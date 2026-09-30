"""Verify bundled evidence hashes and recompute summaries without calling a model."""
import hashlib
import json
from pathlib import Path

from aclab.comparison import paired_effects
from aclab.evidence import implementation_fingerprint, load_run
from aclab.metrics import paired_differences
from aclab.registry import Registry


def main():
    root = Path(__file__).resolve().parents[1]
    verification = json.loads((root / "evidence/verification.json").read_text())
    for relative, expected in verification["source_sha256"].items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected, f"Source changed: {relative}"
    for relative in verification["benchmark_directories"]:
        directory = root / relative
        run = load_run(directory)
        manifest, rows = run.manifest, run.rows
        assert Registry().hash == manifest["contract_hash"], f"Contract changed: {relative}"
        assert implementation_fingerprint() == manifest["implementation_hash"], f"Implementation changed: {relative}"
        recomputed = {"variants": run.summary, "paired": paired_differences(rows, next(iter(manifest["settings"])), manifest["seed"])}
        assert recomputed == json.loads((directory / "summary.json").read_text()), f"Summary changed: {relative}"
        print(f"Verified {relative}: {len(rows)} episodes")
    for relative, expected in verification.get("generated_sha256", {}).items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected, f"Generated artifact changed: {relative}"
    if verification.get("comparison_directory"):
        comparison = json.loads((root / verification["comparison_directory"] / "comparison.json").read_text())
        variants = {}
        seeds = {}
        for record in comparison["records"]:
            run = load_run(root / record["run"])
            assert run.summary[record["variant"]] == record["summary"], f"Comparison summary changed: {record['id']}"
            variants[record["id"]] = [r for r in run.rows if r["variant"] == record["variant"]]
            seeds[record["id"]] = run.manifest["seed"]
        for entry in comparison["comparisons"]:
            if entry["paired_eligible"]:
                computed = paired_effects(variants[entry["baseline"]], variants[entry["candidate"]], seeds[entry["baseline"]])
                assert entry["paired"] == computed, f"Paired comparison changed: {entry['candidate']}"
            else:
                assert entry["paired"] is None and entry["incompatibility_reasons"]
        print(f"Verified {verification['comparison_directory']}: {len(comparison['records'])} variants")
    print("Hashes, episode coverage, and recomputed summaries match. This verifies consistency, not real-model effectiveness.")


if __name__ == "__main__":
    main()
