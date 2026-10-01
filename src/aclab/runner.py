from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import asdict

import httpx

from .evaluators import Evaluator, SemanticCache
from .gateway import Gateway
from .providers import ModelProvider
from .registry import Registry, Validator
from .sandbox import Sandbox, Task, labeled_call_safe, score
from .types import Actor, ExperimentConfig, LabError


class Runner:
    def __init__(self, config: ExperimentConfig, client=None, cache=None, registry=None):
        import os
        self.config = config
        self.client = client or httpx.AsyncClient(limits=httpx.Limits(max_connections=max(8, config.concurrency * 2), max_keepalive_connections=max(4, config.concurrency)), timeout=30, follow_redirects=False, trust_env=False)
        self.owns_client = client is None
        self.registry = registry or Registry()
        self.cache = cache or SemanticCache(config.cache, config.cache_ttl_s, os.environ.get(config.redis_env))
        self.owns_cache = cache is None
        self.provider = ModelProvider(config.provider, self.client)
        self.evaluator = Evaluator(config.evaluator, self.client, self.cache)
        self.validator = Validator(self.registry, config.validator, config.one_url, self.client, config.blaze_worker_path)
        self.gateway = Gateway(config, self.registry, self.validator, self.evaluator)
        self.slots = asyncio.Semaphore(config.concurrency)

    async def close(self):
        if hasattr(self.validator, "close"):
            await self.validator.close()
        if self.owns_client:
            await self.client.aclose()
        if self.owns_cache:
            await self.cache.close()

    async def run(self, task: Task, repeat=0, actor: Actor | None = None):
        queued = time.perf_counter()
        async with self.slots:
            started = time.perf_counter()
            episode_id = str(uuid.uuid4())
            sandbox = Sandbox(task)
            actor = actor or task.actor
            trace, history, model_calls, error = [], [], 0, None
            costs = []
            usage_records = []
            final = ""
            finish_reason = "step_limit"
            try:
                async with asyncio.timeout(self.config.episode_timeout_s):
                    for step in range(self.config.max_steps):
                        before = time.perf_counter()
                        model_calls += 1
                        proposal = await self.provider.propose(task.prompt, self.registry.tool_descriptions(self.config.docs), history, mistake=task.mock_mistake)
                        usage_records.append(asdict(proposal.usage))
                        costs.append(proposal.usage.usd)
                        trace.append({"stage": "model", "step": step, "latency_ms": (time.perf_counter() - before) * 1000, "usage": asdict(proposal.usage), "call_count": len(proposal.calls)})
                        if not proposal.calls:
                            final, finish_reason = proposal.text, "model_finished"
                            break
                        for call in proposal.calls:
                            feedback = await self.gateway.process(call, sandbox, actor, task.prompt, episode_id)
                            record = {"stage": "gateway", "step": step, "call": call.model_dump(), "feedback": feedback}
                            trace.append(record)
                            history.append({"call": call.model_dump(exclude={"call_id"}), "feedback": {k: v for k, v in feedback.items() if k not in ("stages", "latency_ms", "semantic")}})
                            semantic = feedback.get("semantic")
                            if semantic:
                                costs.append(semantic["usage"]["usd"])
                                usage_records.append(semantic["usage"])
                            elif feedback.get("usage_unknown"):
                                costs.append(None)
                                usage_records.append({"input_tokens": None, "output_tokens": None, "attempts": 1})
                            if feedback["code"] in ("OUTCOME_UNKNOWN", "VALIDATOR_UNAVAILABLE", "REGISTRY_DRIFT", "SEMANTIC_INVALID", "SEMANTIC_UNAVAILABLE"):
                                finish_reason = "terminal_feedback"
                                if feedback["code"] != "OUTCOME_UNKNOWN":
                                    error = feedback["code"]
                                break
                        if finish_reason == "terminal_feedback":
                            break
            except TimeoutError:
                error, finish_reason = "EPISODE_TIMEOUT", "error"
            except LabError as exc:
                error, finish_reason = exc.code, "error"
            except (httpx.HTTPError, ValueError, TypeError):
                error, finish_reason = "INTEGRATION_ERROR", "error"
            if error:
                costs.append(None)
                usage_records.append({"input_tokens": None, "output_tokens": None, "attempts": 1})
                trace.append({"stage": "error", "code": error})
            elapsed = time.perf_counter() - started
            # Fixture scoring is an offline measurement step, excluded from task timing.
            scoring_started = time.perf_counter()
            for record in trace:
                if record["stage"] == "gateway":
                    call = record["call"]
                    record["fixture_label_safe"] = labeled_call_safe(task, call)
                    record["fixture_schema_valid"] = not self.registry.local_validate(call["tool_id"], "input", call["arguments"]) if call["tool_id"] in self.registry.contracts else False
            metrics = score(task, sandbox)
            state_goal_satisfied = metrics["task_success"]
            episode_completed = finish_reason == "model_finished" and error is None
            calls = [t for t in trace if t["stage"] == "gateway"]
            known_cost = all(c is not None for c in costs)
            infra = self.config.infra_usd_per_second * elapsed if self.config.infra_usd_per_second is not None else None
            provider_cost = sum(costs) if known_cost else None
            # Mock infrastructure cost remains unknown unless explicitly configured; never claim net savings.
            total_cost = provider_cost + infra if provider_cost is not None and infra is not None else None
            result = {
                "episode_id": episode_id, "task_id": task.id, "category": task.category, "fault": task.fault, "repeat": repeat,
                "provider": self.config.provider.kind, "requested_model": self.config.provider.model,
                "docs": self.config.docs, "enforcement": self.config.enforcement, "validator": self.config.validator,
                "evaluator": self.config.evaluator.kind, "cache": self.config.cache,
                "evidence_kind": "scripted_demo" if self.config.provider.kind == "mock" else "live_model",
                "evaluator_evidence_kind": "scripted_demo" if self.config.evaluator.kind == "mock" else self.config.evaluator.kind,
                "latency_ms": elapsed * 1000, "queue_ms": (started - queued) * 1000,
                "validator_engine": self.config.validator,
                "offline_scoring_ms": (time.perf_counter() - scoring_started) * 1000,
                "model_calls": model_calls, "proposed_calls": len(calls), "blocked_calls": sum(c["feedback"]["decision"] == "blocked" for c in calls),
                "review_calls": sum(c["feedback"]["decision"] == "review" for c in calls),
                "schema_invalid_proposals": sum(not c["fixture_schema_valid"] for c in calls),
                "unsafe_proposals": sum(not c["fixture_label_safe"] for c in calls),
                "false_blocks": sum(c["fixture_label_safe"] and c["fixture_schema_valid"] and c["feedback"]["decision"] in ("blocked", "review") for c in calls),
                "valid_safe_proposals": sum(c["fixture_label_safe"] and c["fixture_schema_valid"] for c in calls),
                "cache_hits": sum(bool(c["feedback"].get("semantic", {}).get("cache_hit")) for c in calls if c["feedback"].get("semantic")),
                "provider_cost_usd": provider_cost, "infra_cost_usd": infra, "total_cost_usd": total_cost,
                "usage_complete": all(u["input_tokens"] is not None and u["output_tokens"] is not None for u in usage_records),
                "retry_cost_may_be_incomplete": any(u["attempts"] > 1 for u in usage_records),
                "error": error, "finish_reason": finish_reason, "trace": trace,
                "state_goal_satisfied": state_goal_satisfied, "episode_completed": episode_completed,
                "input_tokens": sum(u["input_tokens"] for u in usage_records) if all(u["input_tokens"] is not None for u in usage_records) else None,
                "output_tokens": sum(u["output_tokens"] for u in usage_records) if all(u["output_tokens"] is not None for u in usage_records) else None,
                "final": final, "final_state": {"issue": sandbox.issue, "order": sandbox.order}, **metrics
            }
            # Infrastructure errors do not turn no-op goals into successful model runs.
            if error:
                result["task_success"] = result["safe_success"] = False
            if not episode_completed:
                result["safe_success"] = False
            return result
