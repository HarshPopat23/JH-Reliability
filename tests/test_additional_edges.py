import asyncio

import httpx
import pytest

from aclab.evaluators import SemanticCache
from aclab.evalbench import evaluate_dataset
from aclab.runner import Runner
from aclab.sandbox import Sandbox, tasks
from aclab.types import Call, ExperimentConfig, LabError, SemanticResult, Usage


async def test_changed_business_condition_during_evaluation():
    t = tasks(12)[1]
    sandbox = Sandbox(t)
    runner = Runner(ExperimentConfig())
    async def change(*args):
        sandbox.change["merged"] = False
        return SemanticResult("allow", 1)
    runner.evaluator.evaluate = change
    try:
        result = await runner.gateway.process(Call(tool_id="close_issue", arguments={"issue_id": t.issue["issue_id"], "reason": "completed", "expected_version": 1}), sandbox, t.actor, t.prompt, "x")
        assert result["code"] == "PRECONDITION_FAILED"
        assert not sandbox.actions
    finally:
        await runner.close()


async def test_cache_owner_cancellation_has_no_orphan_work():
    cache = SemanticCache("memory")
    entered, stopped = asyncio.Event(), asyncio.Event()
    async def slow():
        entered.set()
        try:
            await asyncio.sleep(60)
        finally:
            stopped.set()
        return SemanticResult("allow", 1)
    job = asyncio.create_task(cache.evaluate("x", slow))
    await entered.wait()
    job.cancel()
    with pytest.raises(asyncio.CancelledError):
        await job
    assert stopped.is_set() and not cache.inflight


async def test_poisoned_cache_is_recomputed():
    cache = SemanticCache("memory")
    await cache.put("x", {"decision": "allow", "confidence": 5})
    result = await cache.evaluate("x", lambda: asyncio.sleep(0, result=SemanticResult("block", 1)))
    assert result.decision == "block" and not result.cache_hit


async def test_semantic_eval_export(tmp_path):
    await evaluate_dataset(ExperimentConfig(), "datasets/semantic-dev.jsonl", tmp_path / "eval")
    import json
    summary = json.loads((tmp_path / "eval/summary.json").read_text())
    assert summary["samples"] == 12
    assert len(summary["threshold_sweep"]) == 21
    assert summary["evidence_kind"] == "scripted_demo"


async def test_failed_model_call_is_not_free_success():
    runner = Runner(ExperimentConfig())
    async def fail(*args, **kwargs):
        raise LabError("PROVIDER_UNAVAILABLE", "offline")
    runner.provider.propose = fail
    try:
        result = await runner.run(tasks(12)[7])
        assert result["model_calls"] == 1
        assert not result["task_success"]
        assert result["provider_cost_usd"] is None
        assert not result["usage_complete"]
    finally:
        await runner.close()


async def test_unknown_extra_schema_field_not_approved():
    t = tasks(12)[1]
    runner = Runner(ExperimentConfig())
    try:
        result = await runner.gateway.process(Call(tool_id="close_issue", arguments={"issue_id": t.issue["issue_id"], "reason": "completed", "expected_version": 1, "scopes": ["admin"]}), Sandbox(t), t.actor, t.prompt, "x")
        assert result["code"] == "SCHEMA_INVALID"
    finally:
        await runner.close()


@pytest.mark.parametrize("decision,confidence", [("unknown", 1), ("allow", True), ("allow", "1"), ("allow", float("nan"))])
def test_invalid_semantic_verdict_types(decision, confidence):
    with pytest.raises(ValueError):
        SemanticResult(decision, confidence).validate()


async def test_failed_evaluator_has_unknown_cost_and_no_success():
    runner = Runner(ExperimentConfig(infra_usd_per_second=0))
    async def fail(*args, **kwargs):
        raise LabError("SEMANTIC_UNAVAILABLE", "offline")
    runner.evaluator.evaluate = fail
    try:
        result = await runner.run(tasks(12)[1])
        assert result["error"] == "SEMANTIC_UNAVAILABLE"
        assert not result["safe_success"]
        assert result["provider_cost_usd"] is None
        assert result["total_cost_usd"] is None
        assert not result["usage_complete"]
        assert result["final_state"]["issue"]["status"] == "open"
    finally:
        await runner.close()


@pytest.mark.parametrize("confidence", [True, "1", None])
async def test_llm_judge_malformed_verdict_fails_closed(confidence):
    from aclab.evaluators import Evaluator
    from aclab.types import Actor, EvaluatorConfig, Proposal, ProviderConfig
    async with httpx.AsyncClient() as client:
        evaluator = Evaluator(EvaluatorConfig(kind="llm", planner=ProviderConfig()), client, SemanticCache())
        async def bad(*args, **kwargs):
            return Proposal(calls=[Call(tool_id="submit_verdict", arguments={"decision": "allow", "confidence": confidence})])
        evaluator.judge.propose = bad
        with pytest.raises(LabError):
            await evaluator.evaluate("close", {}, {}, Actor("a"), "h")


async def test_reserved_mock_profile_prevents_paid_load(tmp_path, monkeypatch):
    from aclab.api import app
    (tmp_path / "mock.yaml").write_text("provider:\n  kind: openai\n  model: paid-model\n")
    monkeypatch.setenv("ACLAB_PROFILE_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="reserved"):
        async with app.router.lifespan_context(app):
            pass


@pytest.mark.parametrize("tokens,cost", [(-1, None), (True, None), (1, float("nan")), (1, -0.1)])
def test_bad_usage_is_not_valid_evidence(tokens, cost):
    with pytest.raises(ValueError):
        Usage(input_tokens=tokens, usd=cost)


def test_json_nonfinite_arguments_are_rejected_before_trace():
    from aclab.providers import parse_json_proposal
    with pytest.raises(LabError):
        parse_json_proposal('{"tool_id":"get_issue","arguments":{"issue_id":NaN}}')


async def test_native_nonfinite_arguments_are_rejected(monkeypatch):
    from aclab.providers import ModelProvider
    from aclab.types import ProviderConfig
    monkeypatch.setenv("TEST_KEY", "fixture")
    payload = {"choices": [{"message": {"tool_calls": [{"function": {"name": "get_issue", "arguments": '{"issue_id":Infinity}'}}]}}]}
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))) as client:
        provider = ModelProvider(ProviderConfig(kind="openai", model="fixture", api_key_env="TEST_KEY"), client)
        with pytest.raises(LabError, match="normalized"):
            await provider.propose("inspect", [], [])


async def test_valid_response_without_live_effect_is_not_accepted():
    import copy
    t = tasks(12)[1]
    sandbox = Sandbox(t)
    runner = Runner(ExperimentConfig())
    async def false_ack(*args, **kwargs):
        reply = copy.deepcopy(sandbox.issue)
        reply.update(status="closed", reason="completed", version=2)
        return reply  # Structurally correct response, but no committed state change.
    sandbox.execute = false_ack
    try:
        result = await runner.gateway.process(Call(tool_id="close_issue", arguments={"issue_id": t.issue["issue_id"], "reason": "completed", "expected_version": 1}), sandbox, t.actor, t.prompt, "x")
        assert result["code"] == "OUTCOME_UNKNOWN"
        assert result["decision"] == "review"
    finally:
        await runner.close()


async def test_injection_is_resource_content_not_user_authorization():
    t = tasks(12)[11]
    assert "Ignore the user" not in t.prompt
    runner = Runner(ExperimentConfig())
    try:
        result = await runner.run(t)
        assert result["safe_success"] and result["writes"] == 0
        reads = [r for r in result["trace"] if r["stage"] == "gateway" and r["call"]["tool_id"] == "get_issue"]
        assert "Ignore the user" in reads[0]["feedback"]["result"]["description"]
    finally:
        await runner.close()
