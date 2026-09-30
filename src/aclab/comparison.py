"""Offline comparisons with explicit alignment and experimental-control checks."""
from __future__ import annotations

import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

from .evidence import load_run
from .metrics import percentile
from .reporting import write_html


def flatten(value, prefix=""):
    result = {}
    if isinstance(value, dict) and value:
        for key, child in value.items():
            result.update(flatten(child, f"{prefix}.{key}" if prefix else key))
    else:
        result[prefix] = value
    return result


def paired_effects(left, right, seed=42, samples=2000):
    a = {(r["task_id"], r["repeat"]): r for r in left}
    b = {(r["task_id"], r["repeat"]): r for r in right}
    if set(a) != set(b):
        raise ValueError("Paired comparisons require complete, identical episode keys")
    clustered = defaultdict(list)
    keys = sorted(a)
    for key in keys:
        clustered[key[0]].append((float(b[key]["safe_success"]) - float(a[key]["safe_success"]), b[key]["latency_ms"] - a[key]["latency_ms"]))
    values = [tuple(statistics.mean(v[i] for v in group) for i in (0, 1)) for group in clustered.values()]
    rng = random.Random(seed)
    draws = [[], []]
    for _ in range(samples):
        sample = rng.choices(values, k=len(values))
        for i in (0, 1):
            draws[i].append(statistics.mean(v[i] for v in sample))
    cis = [[percentile(draws[i], q) for q in (.025, .975)] for i in (0, 1)]
    costs_known = all(r["total_cost_usd"] is not None and not r.get("retry_cost_may_be_incomplete") for r in left + right)
    return {
        "paired_episodes": len(keys), "paired_tasks": len(clustered),
        "safe_success_difference": statistics.mean(v[0] for v in values), "safe_success_ci95_task_cluster": cis[0],
        "latency_mean_difference_ms": statistics.mean(v[1] for v in values), "latency_mean_ci95_task_cluster_ms": cis[1],
        "p95_latency_difference_ms_descriptive": percentile([b[k]["latency_ms"] for k in keys], .95) - percentile([a[k]["latency_ms"] for k in keys], .95),
        "mean_cost_difference_usd": statistics.mean(b[k]["total_cost_usd"] - a[k]["total_cost_usd"] for k in keys) if costs_known else None,
        "unsafe_action_difference": sum(b[k]["unsafe_actions"] - a[k]["unsafe_actions"] for k in keys),
        "note": "Differences are candidate minus baseline. Confidence intervals resample task IDs with all repeats; they do not establish generalization beyond the sampled templates. p95 differences are descriptive and have no interval here.",
    }


def compare_runs(directories, baseline, output, vary=None, max_bytes=128 * 1024 * 1024):
    if not directories:
        raise ValueError("Provide at least one run directory")
    runs = [load_run(p, max_bytes=max_bytes) for p in directories]
    if baseline is None:
        baseline = "0:" + next(iter(runs[0].manifest["settings"]))
    index, separator, variant = baseline.partition(":")
    if not separator or not index.isdigit() or int(index) >= len(runs) or variant not in runs[int(index)].summary:
        raise ValueError("Baseline must be RUN_INDEX:VARIANT, for example 0:baseline")
    base_run = runs[int(index)]
    base_setting = flatten(base_run.manifest["settings"][variant])
    base_rows = [r for r in base_run.rows if r["variant"] == variant]
    permitted = set(vary if vary is not None else ("provider", "docs", "enforcement", "evaluator", "cache"))
    records, comparisons = [], []
    for i, run in enumerate(runs):
        for name, summary in run.summary.items():
            identity = f"{i}:{name}"
            setting = run.manifest["settings"][name]
            records.append({"id": identity, "run": str(run.path), "variant": name, "provider": setting["provider"]["kind"], "model": setting["provider"]["model"], "evaluator": setting["evaluator"]["kind"], "evidence_kind": run.manifest["evidence_kind"], "scoring_version": run.manifest.get("scoring_version", "legacy-v1"), "summary": summary, "warnings": run.warnings})
            if identity == baseline:
                continue
            different = flatten(setting)
            fields = sorted(k for k in set(base_setting) | set(different) if base_setting.get(k) != different.get(k))
            def root(field):
                return {"one_url": "validator", "cache_ttl_s": "cache", "redis_env": "cache"}.get(field, field.split(".")[0])
            controls = [f for f in fields if root(f) not in permitted]
            reasons = []
            for field in ("task_hash", "contract_hash", "scoring_version", "implementation_hash"):
                left, right = base_run.manifest.get(field), run.manifest.get(field)
                if left is None or right is None:
                    reasons.append(f"Missing {field}")
                elif left != right:
                    reasons.append(f"Different {field}")
            candidate = [r for r in run.rows if r["variant"] == name]
            if {(r["task_id"], r["repeat"]) for r in base_rows} != {(r["task_id"], r["repeat"]) for r in candidate}:
                reasons.append("Different task/repeat coverage")
            if controls:
                reasons.append("Control settings differ outside declared treatment factors")
            comparisons.append({"baseline": baseline, "candidate": identity, "paired_eligible": not reasons,
                                "incompatibility_reasons": reasons, "changed_fields": fields, "control_differences": controls,
                                "paired": None if reasons else paired_effects(base_rows, candidate, base_run.manifest["seed"])})
    report = {"schema_version": "1", "baseline": baseline, "declared_treatment_factors": sorted(permitted),
              "records": records, "comparisons": comparisons,
              "note": "This compares stored evidence and performs no inference. Hashes establish internal consistency, not authenticity. Separate runs can differ in provider load and hardware; timing differences are workload-specific. No model is ranked when controls or coverage differ. Scripted results are not model-quality evidence."}
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "comparison.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    write_html(destination / "report.html", report)
    return report
