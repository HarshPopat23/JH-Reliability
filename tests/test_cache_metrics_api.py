import asyncio
from dataclasses import replace

import httpx
import pytest

from aclab.api import app
from aclab.cli import load_config, variants
from aclab.evaluators import Evaluator, SemanticCache
from aclab.metrics import paired_differences, percentile, summarize
from aclab.types import Actor, EvaluatorConfig, ExperimentConfig, SemanticResult, Usage


async def test_cache_singleflight_and_ttl():
    cache = SemanticCache("memory", ttl=.02)
    calls = 0
    async def factory():
        nonlocal calls
        calls += 1
        await asyncio.sleep(.001)
        return SemanticResult("allow", 1, {"allow": 1, "block": 0, "review": 0}, Usage(usd=.01))
    results = await asyncio.gather(*(cache.evaluate("key", factory) for _ in range(20)))
    assert calls == 1 and sum(not r.cache_hit for r in results) == 1
    assert sum(r.usage.usd for r in results) == pytest.approx(.01)
    await asyncio.sleep(.025)
    assert not (await cache.evaluate("key", factory)).cache_hit
    assert calls == 2


async def test_cache_dependencies_are_not_stale():
    cache = SemanticCache("memory")
    async with httpx.AsyncClient() as client:
        evaluator = Evaluator(EvaluatorConfig(), client, cache)
        call = {"tool_id": "close_issue", "arguments": {"reason": "completed"}}
        actor = Actor("a")
        first = await evaluator.evaluate("Close issue", call, {"version": 1}, actor, "h")
        assert not first.cache_hit
        assert (await evaluator.evaluate("Close issue", call, {"version": 1}, actor, "h")).cache_hit
        changes = [({"version": 2}, actor, "h", call), ({"version": 1}, replace(actor, tenant="other"), "h", call), ({"version": 1}, replace(actor, scopes=()), "h", call), ({"version": 1}, actor, "h2", call), ({"version": 1}, actor, "h", {**call, "arguments": {"reason": "not_planned"}})]
        for evidence, who, hash_, proposed in changes:
            assert not (await evaluator.evaluate("Close issue", proposed, evidence, who, hash_)).cache_hit


async def test_broken_redis_recomputes_instead_of_approving():
    cache = SemanticCache("memory")
    async def fail(*args):
        raise RuntimeError("offline")
    cache.get = fail
    cache.put = fail
    result = await cache.evaluate("x", lambda: asyncio.sleep(0, result=SemanticResult("block", 1)))
    assert result.decision == "block"


def test_pass_power_is_all_trials_and_pairing_is_clustered():
    rows = []
    for variant, outcomes in [("baseline", [True, False]), ("full", [True, True])]:
        for repeat, outcome in enumerate(outcomes):
            rows.append({"variant": variant, "task_id": "a", "repeat": repeat, "safe_success": outcome, "task_success": outcome, "category": "x", "latency_ms": 10, "unsafe_actions": 0, "unsafe_proposals": 0, "false_blocks": 0, "valid_safe_proposals": 1, "model_calls": 1, "error": None, "cache_hits": 0, "total_cost_usd": None, "evidence_kind": "scripted_demo"})
    summary = summarize(rows, 2)
    assert summary["baseline"]["safe_success_rate"] == .5
    assert summary["baseline"]["pass_power_k"]["value"] == 0
    assert summary["full"]["pass_power_k"]["value"] == 1
    assert summary["full"]["total_cost_usd"] is None
    assert paired_differences(rows, "baseline")["full"]["safe_success_difference"] == .5


def test_config_yaml_off_and_env(monkeypatch, tmp_path):
    assert load_config("configs/mock.yaml").cache == "off"
    monkeypatch.setenv("ACLAB_TEST_MODEL", "fixture")
    path = tmp_path / "config.yaml"
    path.write_text('provider:\n  kind: ollama\n  model: ${ACLAB_TEST_MODEL}\nevaluator:\n  kind: none\nenforcement: policy\ncache: off\n')
    assert load_config(path).provider.model == "fixture"


async def test_api_auth_actor_injection_and_unknown_profile(monkeypatch):
    monkeypatch.setenv("ACLAB_API_KEY", "fixture-api-key")
    monkeypatch.delenv("ACLAB_PROFILE_DIR", raising=False)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/health")).status_code == 200
        assert (await client.post("/run", json={})).status_code == 401
        headers = {"Authorization": "Bearer fixture-api-key"}
        assert (await client.post("/run", json={"actor": {"scopes": ["admin"]}}, headers=headers)).status_code == 422
        assert (await client.post("/run", json={"profile": "unknown"}, headers=headers)).status_code == 404
        assert (await client.post("/run", json={"task_index": 1}, headers=headers)).json()["safe_success"]
        assert (await client.post("/run", content="x" * 9000, headers=headers)).status_code == 413


async def test_api_backpressure(monkeypatch):
    monkeypatch.setenv("ACLAB_MAX_ACTIVE", "1")
    monkeypatch.delenv("ACLAB_API_KEY", raising=False)
    monkeypatch.delenv("ACLAB_PROFILE_DIR", raising=False)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        app.state.active = 1  # Another admitted episode occupies this worker.
        assert (await client.post("/run", json={})).status_code == 429
        assert (await client.get("/metrics")).json()["rejected"] == 1
