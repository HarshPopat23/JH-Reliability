"""Independent semantic evaluator benchmark; labels never enter evaluator inputs."""
import asyncio
import json
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import httpx

from .evaluators import Evaluator, SemanticCache
from .metrics import percentile, wilson
from .types import Actor, LabError, canonical, digest


async def evaluate_dataset(config, dataset_path, output_path):
    rows = [json.loads(line) for line in Path(dataset_path).read_text().splitlines() if line.strip()]
    if not rows or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Evaluator dataset needs unique IDs")
    if any(r["label"] not in ("allow", "block", "review") for r in rows):
        raise ValueError("Unknown evaluator label")
    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=False)
    slots = asyncio.Semaphore(config.concurrency)
    results = []
    async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
        evaluator = Evaluator(config.evaluator, client, SemanticCache("off"))
        async def one(row):
            async with slots:
                start = time.perf_counter()
                try:
                    async with asyncio.timeout(config.episode_timeout_s):
                        answer = await evaluator.evaluate(row["request"], row["call"], row.get("evidence", {}), Actor("semantic-eval-fixture"), "independent-eval")
                    record = {"id": row["id"], "label": row["label"], "answer": asdict(answer), "error": None}
                except (LabError, ValueError, TypeError, TimeoutError) as exc:
                    record = {"id": row["id"], "label": row["label"], "answer": None, "error": exc.code if isinstance(exc, LabError) else type(exc).__name__}
                record["latency_ms"] = (time.perf_counter() - start) * 1000
                return record
        for offset in range(0, len(rows), config.concurrency):
            results.extend(await asyncio.gather(*(one(r) for r in rows[offset:offset + config.concurrency])))
    confusion = Counter((r["label"], r["answer"]["decision"] if r["answer"] else "error") for r in results)
    correct = sum(r["answer"] is not None and r["answer"]["decision"] == r["label"] for r in results)
    sweep = []
    for threshold in [i / 20 for i in range(21)]:
        accepted = [r for r in results if r["answer"] and r["answer"]["decision"] == "allow" and r["answer"]["confidence"] is not None and r["answer"]["confidence"] >= threshold]
        false_accepts = sum(r["label"] != "allow" for r in accepted)
        good = sum(r["label"] == "allow" for r in results)
        sweep.append({"threshold": threshold, "coverage": len(accepted) / len(results), "false_accept_rate_among_accepted": false_accepts / len(accepted) if accepted else None, "false_reject_rate_among_allow_labels": 1 - sum(r["label"] == "allow" for r in accepted) / good if good else None})
    summary = {"evidence_kind": "scripted_demo" if config.evaluator.kind == "mock" else "live_evaluator", "dataset_hash": digest(rows), "dataset": str(dataset_path), "configuration": config.evaluator.model_dump(), "samples": len(rows), "accuracy": correct / len(rows), "accuracy_ci95_wilson": wilson(correct, len(rows)), "confusion_matrix": {truth: {pred: confusion[(truth, pred)] for pred in ("allow", "block", "review", "error")} for truth in ("allow", "block", "review")}, "latency_ms": {f"p{q}": percentile([r["latency_ms"] for r in results], q / 100) for q in (50, 95, 99)}, "threshold_sweep": sweep, "note": "Tiny authored development fixtures, not a validated safety benchmark. Confidence thresholds must be frozen before held-out testing; do not tune on test labels."}
    (output / "examples.jsonl").write_text("".join(canonical(r) + "\n" for r in rows))
    (output / "results.jsonl").write_text("".join(canonical(r) + "\n" for r in results))
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"samples": len(rows), "accuracy": summary["accuracy"], "evidence_kind": summary["evidence_kind"], "output": str(output)}, indent=2))
