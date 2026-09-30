import json

import httpx
import pytest

from aclab.evaluators import Evaluator, SemanticCache
from aclab.providers import ModelProvider, parse_json_proposal
from aclab.registry import Registry, Validator
from aclab.types import Actor, EvaluatorConfig, LabError, ProviderConfig


@pytest.mark.parametrize("kind", ["openai", "openai_compatible", "anthropic", "gemini", "ollama"])
async def test_provider_requests_and_normalization(kind, monkeypatch):
    monkeypatch.setenv("TEST_KEY", "not-a-real-key")
    seen = []
    def handle(request):
        body = json.loads(request.content)
        seen.append(body)
        assert "fixture_label" not in request.content.decode()
        if kind in ("openai", "openai_compatible"):
            assert body["tools"][0]["function"]["name"] == "get_issue"
            return httpx.Response(200, json={"model": "fixture-model", "choices": [{"message": {"tool_calls": [{"id": "a", "function": {"name": "get_issue", "arguments": '{"issue_id":7}'}}]}}], "usage": {"prompt_tokens": 10, "completion_tokens": 3}})
        if kind == "anthropic":
            assert request.headers["x-api-key"] == "not-a-real-key"
            assert body["tools"][0]["input_schema"]["type"] == "object"
            return httpx.Response(200, json={"model": "fixture-model", "content": [{"type": "tool_use", "id": "a", "name": "get_issue", "input": {"issue_id": 7}}], "usage": {"input_tokens": 10, "output_tokens": 3}})
        if kind == "gemini":
            assert request.headers["x-goog-api-key"] == "not-a-real-key"
            assert "$schema" not in body["tools"][0]["functionDeclarations"][0]["parameters"]
            return httpx.Response(200, json={"modelVersion": "fixture-model", "candidates": [{"content": {"parts": [{"functionCall": {"name": "get_issue", "args": {"issue_id": 7}}}]}}], "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 3}})
        assert body["stream"] is False
        return httpx.Response(200, json={"model": "fixture-model", "message": {"tool_calls": [{"function": {"name": "get_issue", "arguments": {"issue_id": 7}}}]}, "prompt_eval_count": 10, "eval_count": 3})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        provider = ModelProvider(ProviderConfig(kind=kind, model="fixture-model", base_url="https://fixture.invalid/v1" if kind == "openai_compatible" else None, api_key_env="TEST_KEY", input_usd_per_million=1, output_usd_per_million=2), client)
        proposal = await provider.propose("Show issue 7", Registry().tool_descriptions("baseline"), [])
    assert len(seen) == 1
    assert proposal.calls[0].arguments == {"issue_id": 7}
    assert proposal.usage.usd == pytest.approx(16 / 1_000_000)


@pytest.mark.parametrize("raw", ["plain prose", "[]", '{"tool_id":"x"}', '{"final":5}', '{"tool_id":"x","arguments":{},"approved":true}'])
def test_json_planner_rejects_malformed(raw):
    with pytest.raises(LabError):
        parse_json_proposal(raw)


async def test_http_retry_and_secret_redaction(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "SECRET")
    seen = []
    def handle(request):
        seen.append(request)
        if len(seen) < 3:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error": "SECRET"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "done"}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        provider = ModelProvider(ProviderConfig(kind="openai", model="fixture", api_key_env="TEST_KEY"), client)
        assert (await provider.propose("x", [], [])).usage.attempts == 3
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(401, json={"error": "SECRET"}))) as client:
        provider = ModelProvider(ProviderConfig(kind="openai", model="fixture", api_key_env="TEST_KEY"), client)
        with pytest.raises(LabError) as error:
            await provider.propose("x", [], [])
        assert "SECRET" not in str(error.value)


async def test_jev_payload_and_probability_validation(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "not-real")
    def handler(request):
        body = json.loads(request.content)
        assert body["questions"]["intent_match"]["type"] == "choice"
        assert "goal" not in body["state"]
        return httpx.Response(200, json={"model": "jev-fixture", "answers": {"intent_match": {"type": "choice", "choice": "allow", "confidence": .9, "probabilities": {"allow": .9, "block": .05, "review": .05}}}, "usage": {"input_tokens": 10, "output_tokens": 2}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        evaluator = Evaluator(EvaluatorConfig(kind="jev", model="jev-fixture", api_key_env="TEST_KEY"), client, SemanticCache())
        result = await evaluator.evaluate("Close it", {"tool_id": "close_issue", "arguments": {}}, {}, Actor("a"), "hash")
        assert result.decision == "allow" and result.confidence == .9


@pytest.mark.parametrize("probabilities", [{"allow": 2, "block": -1, "review": 0}, {"allow": .1, "block": .7, "review": .2}, {"allow": .8}, {"allow": .1, "block": .1, "review": .1}])
async def test_jev_bad_answer_is_rejected(probabilities, monkeypatch):
    monkeypatch.setenv("TEST_KEY", "not-real")
    data = {"answers": {"intent_match": {"type": "choice", "choice": "allow", "confidence": .9, "probabilities": probabilities}}}
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=data))) as client:
        evaluator = Evaluator(EvaluatorConfig(kind="jev", model="fixture", api_key_env="TEST_KEY"), client, SemanticCache())
        with pytest.raises(LabError):
            await evaluator.evaluate("x", {}, {}, Actor("a"), "h")


async def test_one_schema_pin_and_evaluation():
    registry = Registry()
    count = []
    def handler(request):
        count.append(request.method)
        if request.method == "GET":
            assert request.url.path == "/lab/get_issue-input.json"
            assert request.headers["accept"] == "application/schema+json"
            return httpx.Response(200, json=registry.get("get_issue")["input_schema"])
        assert request.url.path == "/self/v1/api/schemas/evaluate/lab/get_issue-input"
        return httpx.Response(200, json={"valid": False})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        validator = Validator(registry, "one", "https://one.invalid", client)
        assert await validator.validate("get_issue", "input", {"issue_id": "wrong"})
        assert await validator.validate("get_issue", "input", {"issue_id": "wrong"})
    assert count == ["GET", "POST", "POST"]


async def test_one_registry_drift_has_no_fallback():
    registry = Registry()
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"type": "string"}))) as client:
        validator = Validator(registry, "one", "https://one.invalid", client)
        with pytest.raises(LabError, match="does not match"):
            await validator.validate("get_issue", "input", {"issue_id": 7})


@pytest.mark.parametrize("identifier,accepted", [("https://one.invalid/lab/get_issue-input", True), ("https://other.invalid/changed", False)])
async def test_one_assigned_identifier_is_narrowly_normalized(identifier, accepted):
    registry = Registry()
    schema = {**registry.get("get_issue")["input_schema"], "$id": identifier}
    def handler(request):
        return httpx.Response(200, json=schema if request.method == "GET" else {"valid": True})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        validator = Validator(registry, "one", "https://one.invalid", client)
        if accepted:
            assert not await validator.validate("get_issue", "input", {"issue_id": 1})
        else:
            with pytest.raises(LabError, match="does not match"):
                await validator.validate("get_issue", "input", {"issue_id": 1})
