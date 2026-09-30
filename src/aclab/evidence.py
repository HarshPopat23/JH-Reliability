"""Read benchmark evidence without inference and fail on incomplete or changed files."""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .metrics import summarize
from .types import ExperimentConfig, digest

SCORING_VERSION = "safe-completion-v2"


def atomic_json(path, value):
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def implementation_fingerprint():
    root = Path(__file__).parent
    files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(root.rglob("*")) if p.is_file() and p.suffix in (".py", ".json") and "__pycache__" not in p.parts}
    return digest(files)


def finite_json(text):
    def invalid(value):
        raise ValueError("Evidence must contain finite JSON")
    return json.loads(text, parse_constant=invalid)


def file_json(path, limit):
    if path.stat().st_size > limit:
        raise ValueError(f"Evidence file exceeds the configured byte limit: {path.name}")
    return finite_json(path.read_text(encoding="utf-8"))


def file_jsonl(path, limit):
    if path.stat().st_size > limit:
        raise ValueError(f"Evidence file exceeds the configured byte limit: {path.name}")
    sha = hashlib.sha256()
    records = []
    with path.open("rb") as stream:
        for line in stream:
            sha.update(line)
            if line.strip():
                records.append(finite_json(line))
    return records, sha.hexdigest()


@dataclass
class LoadedRun:
    path: Path
    manifest: dict
    rows: list[dict]
    summary: dict
    warnings: list[str]


def load_run(directory, max_bytes=128 * 1024 * 1024):
    path = Path(directory)
    try:
        manifest = file_json(path / "manifest.json", max_bytes)
        if manifest.get("schema_version") not in ("1", "2"):
            raise ValueError("Unsupported evidence schema version")
        if manifest.get("status", "completed") != "completed":
            raise ValueError("Run is incomplete; it cannot be compared")
        rows, sha = file_jsonl(path / "episodes.jsonl", max_bytes)
        tasks, _ = file_jsonl(path / "tasks.jsonl", max_bytes)
        if sha != manifest.get("episode_sha256"):
            raise ValueError("Episode hash differs from the manifest")
        if digest(tasks) != manifest.get("task_hash"):
            raise ValueError("Dataset hash differs from the manifest")
        if not rows or not tasks or len(tasks) != manifest["task_count"]:
            raise ValueError("Empty evidence or incorrect task count")
        task_ids = [t["id"] for t in tasks]
        if any(not isinstance(t, str) or not t for t in task_ids) or len(set(task_ids)) != len(task_ids):
            raise ValueError("Task IDs must be nonempty and unique")
        settings = {k: ExperimentConfig.model_validate(v) for k, v in manifest["settings"].items()}
        if not settings or len({v.repeats for v in settings.values()}) != 1:
            raise ValueError("Variants must have a common repeat count")
        repeats = next(iter(settings.values())).repeats
        expected = {(v, t, r) for v in settings for t in task_ids for r in range(repeats)}
        actual = []
        for row in rows:
            actual.append((row["variant"], row["task_id"], row["repeat"]))
            config = settings[row["variant"]]
            for key in ("safe_success", "task_success"):
                if type(row[key]) is not bool:
                    raise ValueError("Outcome labels must be Boolean")
            for key in ("latency_ms", "total_cost_usd"):
                value = row[key]
                if value is None and key == "total_cost_usd":
                    continue
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                    raise ValueError("Latency and known costs must be finite and nonnegative")
            for key in ("unsafe_actions", "unsafe_proposals", "false_blocks", "valid_safe_proposals", "model_calls", "cache_hits", "repeat"):
                if type(row[key]) is not int or row[key] < 0:
                    raise ValueError("Episode counts must be nonnegative integers")
            if row["safe_success"] and (not row["task_success"] or row["unsafe_actions"] or row.get("error")):
                raise ValueError("Safe success contradicts the recorded outcome")
            for field, expected_value in {"provider": config.provider.kind, "requested_model": config.provider.model, "docs": config.docs, "enforcement": config.enforcement, "validator": config.validator, "evaluator": config.evaluator.kind, "cache": config.cache}.items():
                if row[field] != expected_value:
                    raise ValueError(f"Episode settings differ from manifest field: {field}")
            kind = "scripted_demo" if config.provider.kind == "mock" else "live_model"
            if row["evidence_kind"] != kind or manifest["evidence_kind"] != kind:
                raise ValueError("Evidence kind contradicts the selected provider")
            if manifest["schema_version"] == "2":
                if manifest.get("scoring_version") != SCORING_VERSION:
                    raise ValueError("Unsupported scoring version")
                if type(row.get("episode_completed")) is not bool or type(row.get("state_goal_satisfied")) is not bool:
                    raise ValueError("Completion evidence is missing")
                finished = row.get("finish_reason") == "model_finished" and row.get("error") is None
                if row["episode_completed"] != finished:
                    raise ValueError("Completion label contradicts the termination reason")
                if row["safe_success"] and not row["episode_completed"]:
                    raise ValueError("Unfinished episode cannot be a safe success")
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError("Task/repeat/variant coverage is incomplete or duplicated")
        if len(rows) != manifest.get("episode_count") or len(rows) != manifest.get("completed_episodes"):
            raise ValueError("Episode count differs from the manifest")
        warnings = []
        if manifest["schema_version"] == "2":
            contracts = file_json(path / "contracts.json", max_bytes)
            if digest(contracts) != manifest["contract_hash"]:
                raise ValueError("Frozen contract hash differs from the manifest")
            if not isinstance(manifest.get("implementation_hash"), str) or len(manifest["implementation_hash"]) != 64:
                raise ValueError("Implementation fingerprint is missing")
        else:
            warnings.append("Legacy evidence lacks frozen contracts, an implementation fingerprint, and explicit completion accounting")
        summary = summarize(rows, repeats, manifest["seed"])
        return LoadedRun(path, manifest, rows, summary, warnings)
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError("Malformed evidence record or manifest") from exc
