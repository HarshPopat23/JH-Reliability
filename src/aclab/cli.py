from __future__ import annotations

import argparse
import asyncio
import csv
import importlib.metadata
import json
import os
import platform
import random
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv
from pydantic import ValidationError

from .metrics import paired_differences, percentile, summarize
from .runner import Runner
from .sandbox import Task, tasks
from .types import Actor, ExperimentConfig, canonical, digest
from .evidence import SCORING_VERSION, atomic_json, implementation_fingerprint
from . import __version__


def load_config(path):
    load_dotenv(override=False)
    import re
    import copy
    class Yaml12Loader(yaml.SafeLoader):
        pass
    Yaml12Loader.yaml_implicit_resolvers = copy.deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)
    for first, resolvers in Yaml12Loader.yaml_implicit_resolvers.items():
        Yaml12Loader.yaml_implicit_resolvers[first] = [(tag, regex) for tag, regex in resolvers if tag != "tag:yaml.org,2002:bool"]
    Yaml12Loader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|false|True|False|TRUE|FALSE)$"), list("tTfF"))
    def expand(value):
        if isinstance(value, dict):
            return {k: expand(v) for k, v in value.items()}
        if isinstance(value, list):
            return [expand(v) for v in value]
        if isinstance(value, str):
            def replace(match):
                name = match.group(1)
                if not os.environ.get(name):
                    raise ValueError(f"Set {name} before loading this profile")
                return os.environ[name]
            return re.sub(r"\$\{([A-Z][A-Z0-9_]*)\}", replace, value)
        return value
    return ExperimentConfig.model_validate(expand(yaml.load(Path(path).read_text(), Loader=Yaml12Loader) or {}))


def dataset(path, count, seed):
    if not path:
        return tasks(count, seed)
    records = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            item = json.loads(line)
            actor = item.pop("actor")
            actor["scopes"] = tuple(actor.get("scopes", []))
            actor["approvals"] = tuple(actor.get("approvals", []))
            records.append(Task(actor=Actor(**actor), **item))
    if not records or len({t.id for t in records}) != len(records):
        raise ValueError("Dataset must have nonempty, unique task IDs")
    return records


def variants(config, matrix):
    if matrix == "single":
        return {"single": config}
    if matrix == "docs":
        return {d: config.model_copy(update={"docs": d}) for d in ("baseline", "semantics", "counterexamples", "workflows", "recovery")}
    if matrix == "gates":
        levels = ("baseline", "schema", "policy", "full") if config.evaluator.kind != "none" else ("baseline", "schema", "policy")
        return {g: config.model_copy(update={"enforcement": g}) for g in levels}
    if matrix == "cache":
        return {"cache-off": config.model_copy(update={"cache": "off"}), "cache-on": config.model_copy(update={"cache": config.cache if config.cache != "off" else "memory"})}
    result = {
        "baseline": config.model_copy(update={"docs": "baseline", "enforcement": "baseline", "cache": "off"}),
        "rich-docs": config.model_copy(update={"docs": "recovery", "enforcement": "baseline", "cache": "off"}),
        "schema": config.model_copy(update={"docs": "recovery", "enforcement": "schema", "cache": "off"}),
        "policy": config.model_copy(update={"docs": "recovery", "enforcement": "policy", "cache": "off"}),
    }
    if config.evaluator.kind != "none":
        result["full"] = config.model_copy(update={"docs": "recovery", "enforcement": "full", "cache": "off"})
    return result


def write_report(output, summary, paired, manifest):
    lines = ["# Agent Contract Lab experiment", "", f"Evidence: **{manifest['evidence_kind']}**. Mock runs are engineering checks, not model-performance evidence.", "", "| Variant | Safe completion | Task-cluster 95% CI | p95 ms | Unsafe writes | Errors |", "|---|---:|---|---:|---:|---:|"]
    for name, s in summary.items():
        ci = s["safe_success_ci95_task_cluster_bootstrap"]
        lines.append(f"| {name} | {s['safe_success_rate']:.1%} | {ci[0]:.1%}–{ci[1]:.1%} | {s['latency_ms']['p95']:.2f} | {s['unsafe_actions']} | {s['errors']} |")
    lines += ["", "## Interpretation", "", "Compare documentation variants with fixed enforcement and gate variants with fixed descriptions. The combined matrix alone cannot isolate every contribution.", "", "These task-cluster intervals reflect variation within this synthetic dataset. Repeated templates are not independent real-world domains. The benchmark scores actions and final sandbox state, not natural-language answer quality. Missing pricing or infrastructure rates yield null cost, never zero savings. Provider retries can incur unobserved charges.", "", "## Paired differences", "", "```json", json.dumps(paired, indent=2), "```", "", "See manifest.json, tasks.jsonl and episodes.jsonl for exact settings, labels, traces and outcome evidence."]
    lines += ["", "## Completion and accounting", "", "Safe completion requires an explicit finished model turn. Reaching the step budget or stopping with an unknown outcome cannot be counted as safe success, even if the state goal was satisfied.", "", "| Variant | Finished episodes | Step limits | Reviews | Unknown outcomes | Known cost coverage | Successful-task p95 ms | Other-task p95 ms |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, s in summary.items():
        def ms(value):
            return f"{value:.2f}" if value is not None else "unknown"
        lines.append(f"| {name} | {s['episode_completed_count']} | {s['finish_reason_counts'].get('step_limit', 0)} | {s['gateway_decision_counts'].get('review', 0)} | {s['feedback_code_counts'].get('OUTCOME_UNKNOWN', 0)} | {s['cost_accounting']['known_cost_fraction']:.0%} | {ms(s['latency_by_outcome_ms']['safe_success']['p95'])} | {ms(s['latency_by_outcome_ms']['not_safe_success']['p95'])} |")
    (output / "report.md").write_text("\n".join(lines) + "\n")


async def bench(args):
    existed = Path(args.output).exists()
    try:
        await _bench(args)
    except BaseException as exc:
        path = Path(args.output) / "manifest.json"
        if not existed and path.is_file():
            manifest = json.loads(path.read_text())
            manifest.update(status="incomplete", failure_class=type(exc).__name__)
            episodes = path.parent / "episodes.jsonl"
            if episodes.exists():
                with episodes.open("rb") as stream:
                    manifest["completed_episodes"] = sum(bool(line.strip()) for line in stream)
            atomic_json(path, manifest)
        raise


async def _bench(args):
    config = load_config(args.config)
    updates = {k: getattr(args, k) for k in ("repeats", "concurrency") if getattr(args, k) is not None}
    config = ExperimentConfig.model_validate({**config.model_dump(), **updates})
    data = dataset(args.dataset, args.tasks, config.seed)
    settings = variants(config, args.matrix)
    episode_count = len(data) * config.repeats * len(settings)
    if episode_count > args.max_episodes:
        raise ValueError(f"{episode_count} episodes exceed --max-episodes {args.max_episodes}; explicitly raise the limit")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    registry = None
    runners = {}
    for name, setting in settings.items():
        runners[name] = Runner(setting, registry=registry)
        registry = runners[name].registry
    frozen_tasks = [asdict(t) for t in data]
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(), "schema_version": "2", "status": "running",
        "package_version": __version__, "scoring_version": SCORING_VERSION, "implementation_hash": implementation_fingerprint(),
        "evidence_kind": "scripted_demo" if config.provider.kind == "mock" else "live_model",
        "task_count": len(data), "episode_count": episode_count, "task_hash": digest(frozen_tasks),
        "contract_hash": registry.hash, "seed": config.seed, "matrix": args.matrix,
        "settings": {k: v.model_dump() for k, v in settings.items()},
        "python": sys.version, "platform": platform.platform(),
        "dependencies": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
        "statistical_unit": "task ID (clustered over repeats)",
        "baseline_safeguards": ["target authorization", "exact-action approval", "primitive argument checks", "atomic version comparison", "target deduplication"],
        "limitations": ["Synthetic issue/order templates, not official BFCL or tau-bench", "Scripted agents/evaluators are not model evidence", "No unseen-API generalization claim", "Costs exclude unreported upstream retry charges and unknown infrastructure", "Semantic cache warmness is measured as configured; Redis state must be reset between independent studies", "Latency is local workload-specific, not a production SLA"]
    }
    atomic_json(output / "manifest.json", manifest)
    atomic_json(output / "contracts.json", registry.contracts)
    (output / "tasks.jsonl").write_text("".join(canonical(t) + "\n" for t in frozen_tasks))
    jobs = [(name, task, repeat) for name in settings for task in data for repeat in range(config.repeats)]
    random.Random(config.seed).shuffle(jobs)
    slots = asyncio.Semaphore(config.concurrency)
    rows = []
    started = time.perf_counter()
    async def run_one(job):
        name, task, repeat = job
        async with slots:
            row = await runners[name].run(task, repeat)
            row["variant"] = name
            return row
    # Bound both active episodes AND scheduled futures, even for large datasets.
    pending = set()
    iterator = iter(jobs)
    with (output / "episodes.jsonl").open("w") as stream:
        try:
            for _ in range(min(config.concurrency, len(jobs))):
                pending.add(asyncio.create_task(run_one(next(iterator))))
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for completed in done:
                    row = completed.result()
                    rows.append(row)
                    stream.write(canonical(row) + "\n")
                    stream.flush()
                    if len(rows) % 20 == 0 or len(rows) == len(jobs):
                        print(f"Completed {len(rows)}/{len(jobs)} episodes", flush=True)
                    next_job = next(iterator, None)
                    if next_job:
                        pending.add(asyncio.create_task(run_one(next_job)))
        finally:
            for future in pending:
                future.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for runner in runners.values():
                await runner.close()
    summary = summarize(rows, config.repeats, config.seed)
    baseline = next(iter(settings))
    paired = paired_differences(rows, baseline, config.seed)
    manifest["elapsed_s"] = time.perf_counter() - started
    manifest["completed_episodes"] = len(rows)
    manifest["episode_sha256"] = __import__("hashlib").sha256((output / "episodes.jsonl").read_bytes()).hexdigest()
    atomic_json(output / "summary.json", {"variants": summary, "paired": paired})
    scalars = [{k: v for k, v in r.items() if k not in ("trace", "final_state", "final")} for r in rows]
    with (output / "episodes.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(scalars[0]))
        writer.writeheader()
        writer.writerows(scalars)
    write_report(output, summary, paired, manifest)
    manifest["status"] = "completed"
    atomic_json(output / "manifest.json", manifest)
    print(f"Report: {output / 'report.md'}")
    print(json.dumps({name: {k: value[k] for k in ("safe_success_rate", "unsafe_actions", "errors")} for name, value in summary.items()}, indent=2))


async def demo(args):
    config = load_config(args.config)
    runner = Runner(config)
    try:
        task = next(t for t in tasks(12, config.seed) if t.category == args.category)
        result = await runner.run(task)
        print(json.dumps(result, indent=2))
    finally:
        await runner.close()


async def evaluate(args):
    from .evalbench import evaluate_dataset
    await evaluate_dataset(load_config(args.config), args.dataset, args.output)


async def load(args):
    durations, statuses = [], []
    slots = asyncio.Semaphore(args.concurrency)
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
        async def one(index):
            async with slots:
                begin = time.perf_counter()
                try:
                    headers = {"Authorization": f"Bearer {os.environ['ACLAB_API_KEY']}"} if os.environ.get("ACLAB_API_KEY") else {}
                    response = await client.post(args.url.rstrip("/") + "/run", json={"task_index": index % 12, "profile": "mock"}, headers=headers)
                    statuses.append(response.status_code)
                except httpx.HTTPError:
                    statuses.append(0)
                durations.append((time.perf_counter() - begin) * 1000)
        # Bounded chunks prevent an unbounded task queue.
        for offset in range(0, args.requests, args.concurrency):
            await asyncio.gather(*(one(i) for i in range(offset, min(offset + args.concurrency, args.requests))))
    elapsed = time.perf_counter() - started
    result = {"evidence_kind": "local_mock_gateway_load", "requests": len(statuses), "concurrency": args.concurrency, "elapsed_s": elapsed, "requests_per_second": len(statuses) / elapsed, "status_counts": {str(s): statuses.count(s) for s in set(statuses)}, "latency_ms": {f"p{q}": percentile(durations, q / 100) for q in (50, 95, 99)}, "note": "Measures this local deployment only; not live-model throughput or distributed scalability"}
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Local, sandbox-only agent contract experiments")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("demo")
    p.add_argument("--config", default="configs/mock.yaml")
    p.add_argument("--category", default="inspect", choices=[t.category for t in tasks(12)])
    p = sub.add_parser("bench")
    p.add_argument("--config", default="configs/mock.yaml")
    p.add_argument("--matrix", default="combined", choices=["single", "combined", "docs", "gates", "cache"])
    p.add_argument("--tasks", type=int, default=72)
    p.add_argument("--dataset")
    p.add_argument("--repeats", type=int)
    p.add_argument("--concurrency", type=int)
    p.add_argument("--max-episodes", type=int, default=5000)
    p.add_argument("--output", default="results/" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
    p = sub.add_parser("serve")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--workers", type=int, default=1)
    p = sub.add_parser("evaluate")
    p.add_argument("--config", default="configs/mock.yaml")
    p.add_argument("--dataset", default="datasets/semantic-dev.jsonl")
    p.add_argument("--output", default="results/evaluator-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
    p = sub.add_parser("load")
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--requests", type=int, default=100)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--output", default="load-result.json")
    p = sub.add_parser("export-tasks")
    p.add_argument("--tasks", type=int, default=72)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", default="tasks.jsonl")
    p = sub.add_parser("preflight", help="Offline configuration readiness; no provider requests")
    p.add_argument("--config", default="configs/mock.yaml")
    p.add_argument("--matrix", default="combined", choices=["single", "combined", "docs", "gates", "cache"])
    p.add_argument("--tasks", type=int, default=72)
    p.add_argument("--dataset")
    p.add_argument("--repeats", type=int)
    p = sub.add_parser("compare", help="Integrity-checked offline comparison and HTML viewer")
    p.add_argument("runs", nargs="+")
    p.add_argument("--baseline", help="Zero-based RUN_INDEX:VARIANT, e.g. 0:baseline")
    p.add_argument("--vary", nargs="*", choices=["provider", "docs", "enforcement", "evaluator", "cache", "validator"], default=["provider", "docs", "enforcement", "evaluator", "cache"])
    p.add_argument("--max-evidence-mb", type=int, default=128)
    p.add_argument("--output", default="results/compare-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
    args = parser.parse_args()
    try:
        if args.command == "compare":
            if not 1 <= args.max_evidence_mb <= 4096:
                parser.error("--max-evidence-mb must be 1..4096 per input file")
            from .comparison import compare_runs
            result = compare_runs(args.runs, args.baseline, args.output, args.vary, args.max_evidence_mb * 1024 * 1024)
            print(json.dumps({"variants": len(result["records"]), "paired_eligible": sum(c["paired_eligible"] for c in result["comparisons"]), "report": str(Path(args.output) / "report.html"), "inference_requests": 0}, indent=2))
        elif args.command == "preflight":
            from .preflight import check_configuration
            config = load_config(args.config)
            if args.repeats is not None:
                config = ExperimentConfig.model_validate({**config.model_dump(), "repeats": args.repeats})
            count = len(dataset(args.dataset, args.tasks, config.seed))
            result = check_configuration(config, variants(config, args.matrix), count)
            print(json.dumps(result, indent=2))
            if not result["configuration_ready"]:
                raise SystemExit(1)
        elif args.command == "serve":
            load_dotenv(override=False)
            if args.host not in ("127.0.0.1", "localhost", "::1") and not os.environ.get("ACLAB_API_KEY"):
                parser.error("Non-loopback serving requires ACLAB_API_KEY")
            import uvicorn
            uvicorn.run("aclab.api:app", host=args.host, port=args.port, workers=args.workers)
        elif args.command == "export-tasks":
            Path(args.output).write_text("".join(canonical(asdict(t)) + "\n" for t in tasks(args.tasks, args.seed)))
        else:
            if args.command == "load" and (not 1 <= args.concurrency <= 64 or not 1 <= args.requests <= 100000):
                parser.error("load concurrency must be 1..64 and requests 1..100000")
            asyncio.run({"demo": demo, "bench": bench, "load": load, "evaluate": evaluate}[args.command](args))
    except ValidationError as exc:
        parser.error("; ".join(".".join(map(str, item["loc"])) + ": " + item["msg"] for item in exc.errors(include_input=False, include_context=False)))
    except yaml.YAMLError:
        parser.error("Invalid YAML configuration; check syntax")
    except FileExistsError:
        parser.error("Output directory already exists; choose a new --output")
    except (ValueError, FileNotFoundError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
