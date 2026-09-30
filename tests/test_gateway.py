import asyncio
import copy
from dataclasses import replace

import httpx
import pytest

from aclab.registry import Registry
from aclab.runner import Runner
from aclab.sandbox import Sandbox, score, tasks
from aclab.types import Actor, Call, EvaluatorConfig, ExperimentConfig, LabError, SemanticResult, Usage, digest


@pytest.fixture
def registry():
    return Registry()


def task(category="close"):
    return next(t for t in tasks(12) if t.category == category)


@pytest.mark.parametrize("category", ["inspect", "close", "unmerged", "not_planned", "reopen", "refund", "duplicate", "unauthorized", "approval", "cross_tenant", "ambiguous", "prompt_injection"])
async def test_full_demo_has_no_forbidden_writes(category):
    runner = Runner(ExperimentConfig())
    try:
        result = await runner.run(task(category))
        assert result["unsafe_actions"] == 0
        assert result["error"] is None
    finally:
        await runner.close()


@pytest.mark.parametrize("arguments", [None, [], "bad", {"issue_id": True}, {"issue_id": 1.5}, {"issue_id": float("nan")}, {"issue_id": -1}, {"issue_id": 42, "approved": True}, {"issue_id": "42"}])
async def test_invalid_arguments_never_execute(arguments):
    runner = Runner(ExperimentConfig())
    t = task()
    sandbox = Sandbox(t)
    try:
        result = await runner.gateway.process(Call(tool_id="get_issue", arguments=arguments), sandbox, t.actor, t.prompt, "x")
        assert result["decision"] == "blocked"
        assert not sandbox.actions and not sandbox.reads
    finally:
        await runner.close()


async def test_unknown_tool_and_contract_version():
    runner = Runner(ExperimentConfig())
    t = task()
    try:
        for name, version, expected in [("invented", "1.0.0", "UNKNOWN_TOOL"), ("get_issue", "9", "CONTRACT_VERSION_MISMATCH")]:
            result = await runner.gateway.process(Call(tool_id=name, contract_version=version, arguments={"issue_id": t.issue["issue_id"]}), Sandbox(t), t.actor, t.prompt, "x")
            assert result["code"] == expected
    finally:
        await runner.close()


async def test_actor_cannot_be_injected_into_call():
    with pytest.raises(ValueError):
        Call(tool_id="close_issue", arguments={}, actor={"scopes": ["issues:write"]})


async def test_auth_before_paid_semantics():
    runner = Runner(ExperimentConfig())
    t = task("unauthorized")
    async def fail(*args):
        raise AssertionError("Evaluator must not be called")
    runner.evaluator.evaluate = fail
    try:
        result = await runner.gateway.process(Call(tool_id="close_issue", arguments={"issue_id": t.issue["issue_id"], "reason": "not_planned", "expected_version": 1}), Sandbox(t), t.actor, t.prompt, "x")
        assert result["code"] == "PERMISSION_DENIED"
    finally:
        await runner.close()


async def test_approval_binding_and_forgery():
    t = task("approval")
    args = {"order_id": t.order["order_id"], "amount_cents": 15000, "expected_version": 1}
    binding = digest({"tool": "refund_order", "args": args, "subject": t.actor.subject, "tenant": t.actor.tenant})
    approved = replace(t.actor, approvals=(binding,))
    sandbox = Sandbox(t)
    assert not sandbox.approved("refund_order", args, t.actor)
    assert sandbox.approved("refund_order", args, approved)
    assert not sandbox.approved("refund_order", {**args, "amount_cents": 16000}, approved)
    assert not sandbox.approved("refund_order", args, replace(approved, subject="other"))


@pytest.mark.parametrize("fault", ["timeout_before", "timeout_after", "corrupt_output"])
async def test_verified_recovery_exactly_once(fault):
    t = task("refund")
    t.fault = fault
    runner = Runner(ExperimentConfig())
    try:
        result = await runner.run(t)
        assert result["safe_success"]
        assert result["writes"] == 1
        assert result["final_state"]["order"]["refunded_cents"] == 2000
    finally:
        await runner.close()


async def test_partial_update_is_not_blindly_retried():
    t = task("refund")
    t.fault = "partial_update"
    runner = Runner(ExperimentConfig())
    try:
        result = await runner.run(t)
        assert result["writes"] == 1
        assert result["finish_reason"] == "terminal_feedback"
        assert result["trace"][-1]["feedback"]["code"] == "OUTCOME_UNKNOWN"
        assert not result["task_success"]
    finally:
        await runner.close()


async def test_resource_race_refreshes_version():
    t = task("refund")
    t.fault = "state_race"
    runner = Runner(ExperimentConfig())
    try:
        result = await runner.run(t)
        assert result["safe_success"]
        assert any(r.get("feedback", {}).get("code") == "STATE_CONFLICT" for r in result["trace"])
    finally:
        await runner.close()


async def test_concurrent_same_key_is_exactly_once():
    t = task("refund")
    sandbox = Sandbox(t)
    args = {"order_id": t.order["order_id"], "amount_cents": 2000, "expected_version": 1}
    result = await asyncio.gather(*(sandbox.execute("refund_order", args, t.actor, "same-key") for _ in range(30)))
    assert all(r["refunded_cents"] == 2000 for r in result)
    assert len(sandbox.actions) == 1
    with pytest.raises(LabError, match="Key reused"):
        await sandbox.execute("refund_order", {**args, "amount_cents": 1000}, t.actor, "same-key")


async def test_unavailable_or_uncertain_evaluator_never_approves():
    runner = Runner(ExperimentConfig())
    t = task()
    args = {"issue_id": t.issue["issue_id"], "reason": "completed", "expected_version": 1}
    try:
        async def uncertain(*a):
            return SemanticResult("allow", 0.2, usage=Usage(usd=0))
        runner.evaluator.evaluate = uncertain
        sandbox = Sandbox(t)
        result = await runner.gateway.process(Call(tool_id="close_issue", arguments=args), sandbox, t.actor, t.prompt, "x")
        assert result["code"] == "SEMANTIC_UNCERTAIN" and not sandbox.actions
        async def offline(*a):
            raise LabError("SEMANTIC_UNAVAILABLE", "offline")
        runner.evaluator.evaluate = offline
        result = await runner.gateway.process(Call(tool_id="close_issue", arguments=args), sandbox, t.actor, t.prompt, "x")
        assert result["decision"] == "review" and not sandbox.actions
    finally:
        await runner.close()


def test_cel_missing_fields_fail_closed(registry):
    assert registry.check(registry.get("close_issue")["preconditions"], {"issue": {}})


def test_task_oracle_is_not_public():
    t = task()
    assert set(t.public()) == {"task_id", "request"}


async def test_episodes_are_isolated():
    runner = Runner(ExperimentConfig())
    t = task("refund")
    try:
        results = await asyncio.gather(*(runner.run(t, repeat=i) for i in range(12)))
        assert all(r["writes"] == 1 and r["safe_success"] for r in results)
        assert t.order["refunded_cents"] == 0
    finally:
        await runner.close()
