from __future__ import annotations

import asyncio
import time
from dataclasses import asdict

from .evaluators import Evaluator
from .registry import Registry, Validator
from .sandbox import Sandbox
from .types import Actor, Call, ExperimentConfig, LabError, digest


class Gateway:
    def __init__(self, config: ExperimentConfig, registry: Registry, validator: Validator, evaluator: Evaluator):
        self.config, self.registry, self.validator, self.evaluator = config, registry, validator, evaluator

    async def process(self, call: Call, sandbox: Sandbox, actor: Actor, request: str, episode_id: str):
        started = time.perf_counter()
        stages = []
        semantic = None
        attempts = 0
        level = ["baseline", "schema", "policy", "full"].index(self.config.enforcement)

        async def stage(name, work):
            before = time.perf_counter()
            try:
                return await work()
            finally:
                stages.append({"stage": name, "latency_ms": (time.perf_counter() - before) * 1000})

        async def value_stage(name, function):
            async def fn():
                return function()
            return await stage(name, fn)

        def result(decision, code, message, **extra):
            return {"decision": decision, "code": code, "message": message, "stages": stages, "latency_ms": (time.perf_counter() - started) * 1000, "attempts": attempts, "semantic": asdict(semantic) if semantic else None, "usage_unknown": semantic is None and any(s["stage"] == "meaning" for s in stages), **extra}

        try:
            contract = self.registry.get(call.tool_id)
            if call.contract_version != contract["contract_version"]:
                raise LabError("CONTRACT_VERSION_MISMATCH", "Use the pinned tool contract version")
            # Always prevent permission bypass and malformed Python objects, including baseline.
            if not isinstance(call.arguments, dict):
                raise LabError("INVALID_ARGUMENTS", "Arguments must be a JSON object")
            if not sandbox.authorized(call.tool_id, actor):
                raise LabError("PERMISSION_DENIED", "Current authenticated actor cannot access this resource")
            digest(call.arguments)
            if level >= 1:
                errors = await stage("arguments", lambda: self.validator.validate(call.tool_id, "input", call.arguments))
                if errors:
                    return result("blocked", "SCHEMA_INVALID", "; ".join(errors), retryable=False)
            evidence = await value_stage("current_state", lambda: sandbox.evidence(call.tool_id))
            context = {**evidence, "args": call.arguments, "actor": asdict(actor)}
            if level >= 2:
                failed = await value_stage("preconditions", lambda: self.registry.check(contract["preconditions"], context))
                if failed:
                    return result("blocked", "PRECONDITION_FAILED", failed, retryable=False)
            if level >= 3 and contract["semantic_check"]:
                semantic = await stage("meaning", lambda: self.evaluator.evaluate(request, call.model_dump(exclude={"call_id"}), evidence, actor, self.registry.hash))
                if semantic.decision != "allow":
                    code = "SEMANTIC_MISMATCH" if semantic.decision == "block" else "SEMANTIC_UNCERTAIN"
                    return result("blocked" if semantic.decision == "block" else "review", code, semantic.reason, retryable=False)
                if semantic.confidence is None or semantic.confidence < self.config.evaluator.threshold:
                    return result("review", "SEMANTIC_UNCERTAIN", "Evaluator confidence is below the configured threshold", retryable=False)
            # Recheck AFTER evaluation/cache; these results are never cached.
            if not await value_stage("authorization", lambda: sandbox.authorized(call.tool_id, actor)):
                raise LabError("PERMISSION_DENIED", "Current authorization changed")
            if not sandbox.approved(call.tool_id, call.arguments, actor):
                raise LabError("APPROVAL_REQUIRED", "A trusted approval bound to this exact action is required")
            key = digest({"episode": episode_id, "actor": asdict(actor), "tool": call.tool_id, "args": call.arguments, "contract": self.registry.hash})
            output = None
            for attempts in range(1, self.config.tool_attempts + 1):
                try:
                    guard = (lambda: self.registry.check(contract["preconditions"], {**sandbox.evidence(call.tool_id), "args": call.arguments, "actor": asdict(actor)})) if level >= 2 else None
                    output = await stage("execution", lambda: sandbox.execute(call.tool_id, call.arguments, actor, key, guard=guard))
                    break
                except LabError as exc:
                    if not exc.retryable:
                        raise
                    if level >= 2:
                        recovered = await value_stage("reconcile", lambda: sandbox.outcome(call.tool_id, call.arguments, key))
                        if recovered is not None:
                            output = recovered
                            break
                        current = sandbox.evidence(call.tool_id)
                        if digest(current) != digest(evidence):
                            return result("review", "OUTCOME_UNKNOWN", "State changed without verified completion; do not blindly retry", retryable=False)
                    if attempts == self.config.tool_attempts:
                        return result("review", "OUTCOME_UNKNOWN", "Retries exhausted without verified completion", retryable=False)
                    await asyncio.sleep(0.01 * 2 ** (attempts - 1))
            if level >= 1:
                errors = await stage("output_schema", lambda: self.validator.validate(call.tool_id, "output", output))
                if errors:
                    if level >= 2:
                        recovered = await value_stage("reconcile", lambda: sandbox.outcome(call.tool_id, call.arguments, key))
                        if recovered is not None and not await self.validator.validate(call.tool_id, "output", recovered):
                            output = recovered
                        else:
                            return result("review", "OUTCOME_UNKNOWN", "Action may have happened; response is invalid", retryable=False)
                    else:
                        return result("review", "OUTPUT_SCHEMA_INVALID", "Response is invalid; action may have happened", retryable=False)
            if level >= 2:
                after = await value_stage("verify_state", lambda: sandbox.evidence(call.tool_id))
                failed = await value_stage("postconditions", lambda: self.registry.check(contract["postconditions"], {**after, "args": call.arguments, "actor": asdict(actor), "result": output}))
                if failed:
                    return result("review", "OUTCOME_UNKNOWN", failed, retryable=False)
            return result("executed", "OK", "Result accepted under this experiment's checks", result=output, retryable=False)
        except LabError as exc:
            return result("review" if exc.code.startswith(("SEMANTIC", "VALIDATOR", "PROVIDER")) else "blocked", exc.code, exc.message, retryable=exc.retryable)
        except (ValueError, TypeError):
            return result("blocked", "INVALID_ARGUMENTS", "Call must contain finite JSON", retryable=False)
