from __future__ import annotations

import math
import random
import statistics
from collections import Counter, defaultdict


def percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * q
    lower = int(position)
    fraction = position - lower
    return values[lower] * (1 - fraction) + values[min(lower + 1, len(values) - 1)] * fraction


def wilson(successes, count):
    if not count:
        return [None, None]
    z, p = 1.959964, successes / count
    denom = 1 + z * z / count
    center = (p + z * z / (2 * count)) / denom
    radius = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / denom
    return [max(0, center - radius), min(1, center + radius)]


def latency_stats(values):
    values = list(values)
    return {"samples": len(values), "mean": statistics.mean(values) if values else None,
            **{f"p{q}": percentile(values, q / 100) for q in (50, 95, 99)}}


def diagnostics(group):
    stages = defaultdict(list)
    feedback, decisions, finish, errors = Counter(), Counter(), Counter(), Counter()
    models = {"planner": set(), "evaluator": set()}
    for row in group:
        finish[row.get("finish_reason", "unknown")] += 1
        if row.get("error"):
            errors[row["error"]] += 1
        for event in row.get("trace", []):
            if event["stage"] == "model":
                stages["model"].append(event["latency_ms"])
                if event.get("usage", {}).get("model"):
                    models["planner"].add(event["usage"]["model"])
            elif event["stage"] == "gateway":
                response = event["feedback"]
                feedback[response["code"]] += 1
                decisions[response["decision"]] += 1
                for stage in response.get("stages", []):
                    stages[stage["stage"]].append(stage["latency_ms"])
                semantic = response.get("semantic")
                if semantic and semantic.get("usage", {}).get("model"):
                    models["evaluator"].add(semantic["usage"]["model"])
    known = [r["total_cost_usd"] for r in group if r["total_cost_usd"] is not None]
    return {
        "finish_reason_counts": dict(sorted(finish.items())), "error_code_counts": dict(sorted(errors.items())),
        "feedback_code_counts": dict(sorted(feedback.items())),
        "gateway_decision_counts": dict(sorted(decisions.items())),
        "observed_models": {k: sorted(v) for k, v in models.items()},
        "latency_by_outcome_ms": {"safe_success": latency_stats(r["latency_ms"] for r in group if r["safe_success"]), "not_safe_success": latency_stats(r["latency_ms"] for r in group if not r["safe_success"])},
        "queue_ms": latency_stats(r["queue_ms"] for r in group if r.get("queue_ms") is not None),
        "stage_latency_ms": {k: latency_stats(v) for k, v in sorted(stages.items())},
        "cost_accounting": {"known_total_cost_episodes": len(known), "unknown_total_cost_episodes": len(group) - len(known), "known_cost_fraction": len(known) / len(group), "known_subtotal_usd": sum(known) if known else None, "potentially_unreported_retry_cost_episodes": sum(bool(r.get("retry_cost_may_be_incomplete")) for r in group)},
        "usage_reporting": {"complete": sum(r.get("usage_complete") is True for r in group), "incomplete": sum(r.get("usage_complete") is False for r in group), "unknown": sum(r.get("usage_complete") is None for r in group)},
        "episode_completed_count": sum(r.get("episode_completed") is True for r in group),
        "completion_status_unknown_count": sum(r.get("episode_completed") is None for r in group),
        "state_goal_satisfied_but_not_completed": sum(r.get("state_goal_satisfied") is True and r.get("episode_completed") is False for r in group),
    }


def cluster_ci(rows, metric="safe_success", seed=42, samples=2000):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["task_id"]].append(float(row[metric]))
    values = [statistics.mean(v) for v in grouped.values()]
    if not values:
        return [None, None]
    rng = random.Random(seed)
    draws = [statistics.mean(rng.choices(values, k=len(values))) for _ in range(samples)]
    return [percentile(draws, 0.025), percentile(draws, 0.975)]


def summarize(rows, repeats, seed=42):
    groups = defaultdict(list)
    for row in rows:
        groups[row["variant"]].append(row)
    summary = {}
    for variant, group in groups.items():
        by_task = defaultdict(list)
        for row in group:
            by_task[row["task_id"]].append(row)
        complete = [g for g in by_task.values() if len(g) == repeats and len({r["repeat"] for r in g}) == repeats]
        successes = sum(r["safe_success"] for r in group)
        total_costs = [r["total_cost_usd"] for r in group]
        categories = {}
        for category in sorted({r["category"] for r in group}):
            subset = [r for r in group if r["category"] == category]
            categories[category] = {"episodes": len(subset), "safe_success": statistics.mean(r["safe_success"] for r in subset), "unsafe_actions": sum(r["unsafe_actions"] for r in subset)}
        safe_proposals = sum(r["valid_safe_proposals"] for r in group)
        summary[variant] = {
            "episodes": len(group), "tasks": len(by_task),
            "task_success_rate": statistics.mean(r["task_success"] for r in group),
            "safe_success_rate": successes / len(group),
            "safe_success_ci95_task_cluster_bootstrap": cluster_ci(group, seed=seed),
            "pass_power_k": {"k": repeats, "value": statistics.mean(all(r["safe_success"] for r in g) for g in complete) if complete else None, "complete_tasks": len(complete)},
            "latency_ms": {f"p{q}": percentile([r["latency_ms"] for r in group], q / 100) for q in (50, 95, 99)},
            "unsafe_actions": sum(r["unsafe_actions"] for r in group), "unsafe_proposals": sum(r["unsafe_proposals"] for r in group),
            "false_block_rate_fixture": sum(r["false_blocks"] for r in group) / safe_proposals if safe_proposals else None,
            "model_calls_mean": statistics.mean(r["model_calls"] for r in group),
            "errors": sum(r["error"] is not None for r in group),
            "cache_hits": sum(r["cache_hits"] for r in group),
            "total_cost_usd": sum(total_costs) if all(c is not None for c in total_costs) else None,
            "cost_per_safe_success_usd": sum(total_costs) / successes if successes and all(c is not None for c in total_costs) else None,
            "evidence_kind": sorted({r["evidence_kind"] for r in group}), "categories": categories,
            **diagnostics(group),
        }
    return summary


def paired_differences(rows, baseline, seed=42, samples=2000):
    groups = defaultdict(dict)
    for row in rows:
        groups[row["variant"]][(row["task_id"], row["repeat"])] = row
    if baseline not in groups:
        return {}
    result = {}
    for name, group in groups.items():
        if name == baseline:
            continue
        paired = sorted(set(group) & set(groups[baseline]))
        clusters = defaultdict(list)
        for key in paired:
            clusters[key[0]].append(float(group[key]["safe_success"]) - float(groups[baseline][key]["safe_success"]))
        differences = [statistics.mean(v) for v in clusters.values()]
        if not differences:
            continue
        rng = random.Random(seed)
        boot = [statistics.mean(rng.choices(differences, k=len(differences))) for _ in range(samples)]
        result[name] = {"baseline": baseline, "paired_episodes": len(paired), "paired_tasks": len(clusters), "safe_success_difference": statistics.mean(differences), "ci95_task_cluster_bootstrap": [percentile(boot, .025), percentile(boot, .975)]}
    return result
