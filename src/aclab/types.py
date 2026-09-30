from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Call(StrictModel):
    tool_id: str = Field(min_length=1, max_length=128)
    arguments: Any
    contract_version: str = "1.0.0"
    call_id: str = ""


class ProviderConfig(StrictModel):
    kind: Literal["mock", "openai", "openai_compatible", "anthropic", "gemini", "ollama"] = "mock"
    model: str = "scripted-demo"
    base_url: str | None = None
    api_key_env: str | None = None
    mode: Literal["tools", "json"] = "tools"
    timeout_s: float = Field(default=60, gt=0, le=300)
    max_tokens: int = Field(default=1024, ge=64, le=32768)
    temperature: float | None = Field(default=None, ge=0, le=2)
    extra_body: dict[str, Any] = Field(default_factory=dict)
    input_usd_per_million: float | None = Field(default=None, ge=0)
    output_usd_per_million: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def check(self):
        if self.kind != "mock" and (not self.model or self.model == "scripted-demo"):
            raise ValueError("Set an explicit provider model ID")
        if self.kind == "openai_compatible" and not self.base_url:
            raise ValueError("openai_compatible requires base_url")
        reserved = {"messages", "tools", "model", "contents", "system", "systemInstruction", "stream"}
        if reserved & self.extra_body.keys():
            raise ValueError("extra_body cannot override model, messages, tools, or stream")
        return self


class EvaluatorConfig(StrictModel):
    kind: Literal["none", "mock", "jev", "llm"] = "mock"
    model: str = "scripted-rules"
    base_url: str = "https://api.typesafe.ai"
    api_key_env: str = "TYPESAFE_API_KEY"
    threshold: float = Field(default=0.85, ge=0, le=1)
    planner: ProviderConfig | None = None
    input_usd_per_million: float | None = Field(default=None, ge=0)
    output_usd_per_million: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def check(self):
        if self.kind == "jev" and self.model == "scripted-rules":
            raise ValueError("Set an explicit Jev model ID")
        if self.kind == "llm" and self.planner is None:
            raise ValueError("llm evaluator requires a planner configuration")
        return self


class ExperimentConfig(StrictModel):
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    evaluator: EvaluatorConfig = Field(default_factory=EvaluatorConfig)
    docs: Literal["baseline", "semantics", "counterexamples", "workflows", "recovery"] = "recovery"
    enforcement: Literal["baseline", "schema", "policy", "full"] = "full"
    validator: Literal["jsonschema", "one"] = "jsonschema"
    one_url: str = "http://127.0.0.1:8080"
    cache: Literal["off", "memory", "redis"] = "off"
    cache_ttl_s: int = Field(default=60, ge=1, le=3600)
    redis_env: str = "REDIS_URL"
    max_steps: int = Field(default=8, ge=1, le=32)
    tool_attempts: int = Field(default=3, ge=1, le=5)
    episode_timeout_s: float = Field(default=180, gt=0, le=1800)
    concurrency: int = Field(default=4, ge=1, le=64)
    repeats: int = Field(default=3, ge=1, le=20)
    seed: int = 42
    infra_usd_per_second: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def check(self):
        if self.enforcement == "full" and self.evaluator.kind == "none":
            raise ValueError("full requires a semantic evaluator; use policy to disable it")
        return self


@dataclass(frozen=True)
class Actor:
    subject: str
    tenant: str = "demo"
    scopes: tuple[str, ...] = ("issues:read", "issues:write", "orders:read", "orders:write")
    # Approval objects are issued by the trusted fixture/service, never the model.
    approvals: tuple[str, ...] = ()


@dataclass
class Usage:
    input_tokens: int | None = 0
    output_tokens: int | None = 0
    usd: float | None = None
    attempts: int = 1
    model: str = ""

    def __post_init__(self):
        for value in (self.input_tokens, self.output_tokens):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Token usage must be a nonnegative integer or unknown")
        if type(self.attempts) is not int or self.attempts < 1:
            raise ValueError("Attempt count must be a positive integer")
        if self.usd is not None and (isinstance(self.usd, bool) or not isinstance(self.usd, (int, float)) or not math.isfinite(self.usd) or self.usd < 0):
            raise ValueError("Cost must be finite and nonnegative or unknown")

    def price(self, input_rate: float | None, output_rate: float | None):
        if input_rate is not None and output_rate is not None and self.input_tokens is not None and self.output_tokens is not None:
            try:
                self.usd = (self.input_tokens * input_rate + self.output_tokens * output_rate) / 1_000_000
            except OverflowError as exc:
                raise ValueError("Pricing values exceed finite accounting range") from exc
            self.__post_init__()
        return self


@dataclass
class Proposal:
    calls: list[Call] = field(default_factory=list)
    text: str = ""
    usage: Usage = field(default_factory=Usage)


@dataclass
class SemanticResult:
    decision: Literal["allow", "block", "review"]
    confidence: float | None = None
    probabilities: dict[str, float] | None = None
    usage: Usage = field(default_factory=Usage)
    reason: str = ""
    cache_hit: bool = False

    def validate(self):
        if self.decision not in ("allow", "block", "review"):
            raise ValueError("Invalid decision")
        if self.confidence is not None and (isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)) or not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1):
            raise ValueError("Invalid confidence")
        if self.probabilities is not None:
            if not isinstance(self.probabilities, dict):
                raise ValueError("Probabilities must be a label map")
            if set(self.probabilities) != {"allow", "block", "review"}:
                raise ValueError("Unexpected evaluator labels")
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 or v > 1 for v in self.probabilities.values()):
                raise ValueError("Invalid probabilities")
            if abs(sum(self.probabilities.values()) - 1) > 0.02:
                raise ValueError("Probabilities must sum to one")
            if self.probabilities[self.decision] < max(self.probabilities.values()) - 1e-8:
                raise ValueError("Decision is not highest-probability label")
        return self


class LabError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable

    def feedback(self):
        return {"code": self.code, "message": self.message, "retryable": self.retryable}
