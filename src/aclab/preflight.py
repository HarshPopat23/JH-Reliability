"""Offline configuration readiness; never contacts a provider or prints credentials."""
import os

from .registry import Registry
from .types import digest


def planner_key(config):
    if config.kind in ("openai", "anthropic", "gemini"):
        return config.api_key_env or {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}[config.kind]
    return None


def check_configuration(config, settings, task_count):
    registry = Registry()
    needed, dependencies = set(), set()
    key = planner_key(config.provider)
    if key:
        needed.add(key)
    if config.provider.kind in ("ollama", "openai_compatible"):
        dependencies.add("Local or compatible model server")
    for variant in settings.values():
        if variant.enforcement == "full":
            if variant.evaluator.kind == "jev":
                needed.add(variant.evaluator.api_key_env)
            elif variant.evaluator.kind == "llm":
                judge_key = planner_key(variant.evaluator.planner)
                if judge_key:
                    needed.add(judge_key)
                if variant.evaluator.planner.kind in ("ollama", "openai_compatible"):
                    dependencies.add("Local or compatible evaluator server")
        if variant.cache == "redis":
            needed.add(variant.redis_env)
            dependencies.add("Redis")
        if variant.validator == "one":
            dependencies.add("Sourcemeta One")
    missing = sorted(k for k in needed if not os.environ.get(k))
    catalogs = {name: registry.tool_descriptions(v.docs) for name, v in settings.items()}
    return {
        "configuration_ready": not missing, "network_requests": 0,
        "provider": config.provider.kind, "model": config.provider.model, "mode": config.provider.mode,
        "required_environment_names": sorted(needed), "missing_environment_names": missing,
        "external_dependencies_not_checked": sorted(dependencies),
        "planned_episodes": task_count * config.repeats * len(settings),
        "variant_names": list(settings), "contract_hash": registry.hash,
        "catalogs": {k: {"hash": digest(c), "bytes_utf8": len(__import__("json").dumps(c, ensure_ascii=False).encode())} for k, c in catalogs.items()},
        "planner_token_prices_configured": config.provider.kind == "mock" or (config.provider.input_usd_per_million is not None and config.provider.output_usd_per_million is not None),
        "infrastructure_rate_configured": config.infra_usd_per_second is not None,
        "note": "This checks configuration only. It does not verify account access, model availability, server health, token limits, or actual charges. Episode limits are not a dollar cap.",
    }
