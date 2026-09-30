import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from aclab.cli import bench, variants
from aclab.comparison import compare_runs, paired_effects
from aclab.evidence import atomic_json, load_run
from aclab.metrics import summarize
from aclab.preflight import check_configuration
from aclab.runner import Runner
from aclab.sandbox import tasks
from aclab.types import Call, ExperimentConfig, Proposal, ProviderConfig, Usage, canonical, digest


@pytest.fixture
async def recorded_run(tmp_path):
    output = tmp_path / "original"
    await bench(SimpleNamespace(config="configs/mock.yaml", repeats=2, concurrency=2, dataset=None,
                                tasks=4, matrix="single", max_episodes=5000, output=str(output)))
    return output


def save_manifest(directory, mutate):
    path = directory / "manifest.json"
    data = json.loads(path.read_text())
    mutate(data)
    atomic_json(path, data)


def change_rows(directory, mutate):
    path = directory / "episodes.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows = mutate(rows)
    path.write_text("".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in rows))
    save_manifest(directory, lambda m: m.update(episode_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))


async def test_step_limit_cannot_be_safe_noop_success():
    runner = Runner(ExperimentConfig(max_steps=2))
    async def stuck(*args, **kwargs):
        return Proposal([Call(tool_id="unknown_tool", arguments={})], usage=Usage(usd=0))
    runner.provider.propose = stuck
    try:
        row = await runner.run(tasks(12)[10])
        assert row["state_goal_satisfied"]
        assert row["finish_reason"] == "step_limit"
        assert not row["episode_completed"] and not row["safe_success"]
    finally:
        await runner.close()


async def test_met_state_goal_still_needs_finished_episode():
    runner = Runner(ExperimentConfig(max_steps=3))
    try:
        row = await runner.run(tasks(12)[1])
        assert row["state_goal_satisfied"] and row["task_success"]
        assert row["finish_reason"] == "step_limit" and not row["safe_success"]
    finally:
        await runner.close()


async def test_unknown_terminal_feedback_is_not_safe_completion():
    runner = Runner(ExperimentConfig())
    process = runner.gateway.process
    async def uncertain(call, *args):
        feedback = await process(call, *args)
        if call.tool_id == "close_issue" and feedback["code"] == "OK":
            feedback.update(decision="review", code="OUTCOME_UNKNOWN")
        return feedback
    runner.gateway.process = uncertain
    try:
        row = await runner.run(tasks(12)[1])
        assert row["state_goal_satisfied"] and row["finish_reason"] == "terminal_feedback"
        assert not row["safe_success"]
    finally:
        await runner.close()


async def test_complete_artifact_and_offline_comparison(recorded_run, tmp_path):
    run = load_run(recorded_run)
    assert len(run.rows) == 8 and not run.warnings
    second = tmp_path / "copy"
    shutil.copytree(recorded_run, second)
    report = compare_runs([recorded_run, second], "0:single", tmp_path / "comparison", vary=[])
    pair = report["comparisons"][0]
    assert pair["paired_eligible"]
    assert pair["paired"]["safe_success_difference"] == 0
    assert pair["paired"]["latency_mean_ci95_task_cluster_ms"] == [0, 0]
    assert (tmp_path / "comparison/report.html").is_file()


async def test_different_concurrency_refuses_paired_estimate(recorded_run, tmp_path):
    other = tmp_path / "other"
    shutil.copytree(recorded_run, other)
    save_manifest(other, lambda m: m["settings"]["single"].update(concurrency=1))
    result = compare_runs([recorded_run, other], "0:single", tmp_path / "comparison")
    assert not result["comparisons"][0]["paired_eligible"]
    assert result["comparisons"][0]["control_differences"] == ["concurrency"]
    assert result["comparisons"][0]["paired"] is None


@pytest.mark.parametrize("field", ["task_hash", "contract_hash", "implementation_hash"])
async def test_different_evidence_basis_is_flagged(recorded_run, tmp_path, field):
    other = tmp_path / "other"
    shutil.copytree(recorded_run, other)
    if field == "task_hash":
        path = other / "tasks.jsonl"
        examples = [json.loads(x) for x in path.read_text().splitlines()]
        examples[0]["prompt"] += " New task wording."
        path.write_text("".join(canonical(t) + "\n" for t in examples))
        replacement = digest(examples)
    elif field == "contract_hash":
        path = other / "contracts.json"
        contracts = json.loads(path.read_text())
        contracts["get_issue"]["description"] += " changed"
        atomic_json(path, contracts)
        replacement = digest(contracts)
    else:
        replacement = "b" * 64
    save_manifest(other, lambda m: m.update({field: replacement}))
    report = compare_runs([recorded_run, other], "0:single", tmp_path / "comparison")
    assert f"Different {field}" in report["comparisons"][0]["incompatibility_reasons"]
    assert report["comparisons"][0]["paired"] is None


async def test_undeclared_description_treatment_is_flagged(recorded_run, tmp_path):
    other = tmp_path / "other"
    shutil.copytree(recorded_run, other)
    save_manifest(other, lambda m: m["settings"]["single"].update(docs="baseline"))
    def changed(rows):
        for row in rows:
            row["docs"] = "baseline"
        return rows
    change_rows(other, changed)
    report = compare_runs([recorded_run, other], "0:single", tmp_path / "comparison", vary=["evaluator"])
    assert report["comparisons"][0]["control_differences"] == ["docs"]


async def test_truncated_evidence_is_rejected(recorded_run):
    path = recorded_run / "episodes.jsonl"
    lines = path.read_bytes().splitlines(keepends=True)
    path.write_bytes(b"".join(lines[:-1]))
    with pytest.raises(ValueError, match="hash differs"):
        load_run(recorded_run)


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "settings", "nonfinite", "false_success", "false_completion"])
async def test_consistently_rehashed_bad_records_are_rejected(recorded_run, mutation):
    def change(rows):
        if mutation == "duplicate":
            rows[1] = rows[0]
        elif mutation == "missing":
            rows.pop()
        elif mutation == "settings":
            rows[0]["docs"] = "baseline"
        elif mutation == "nonfinite":
            rows[0]["latency_ms"] = float("nan")
        elif mutation == "false_success":
            rows[0].update(safe_success=True, episode_completed=False)
        elif mutation == "false_completion":
            rows[0].update(finish_reason="step_limit", episode_completed=True)
        return rows
    change_rows(recorded_run, change)
    with pytest.raises(ValueError):
        load_run(recorded_run)


async def test_incomplete_run_and_byte_limit_are_rejected(recorded_run):
    with pytest.raises(ValueError, match="byte limit"):
        load_run(recorded_run, max_bytes=1)
    save_manifest(recorded_run, lambda m: m.update(status="incomplete"))
    with pytest.raises(ValueError, match="incomplete"):
        load_run(recorded_run)


async def test_diagnostics_separate_cost_coverage_and_latency(recorded_run):
    rows = load_run(recorded_run).rows
    rows[0]["total_cost_usd"] = None
    rows[0]["retry_cost_may_be_incomplete"] = True
    result = summarize(rows, 2)["single"]
    assert result["total_cost_usd"] is None
    assert result["cost_accounting"]["known_total_cost_episodes"] == 7
    assert result["cost_accounting"]["known_cost_fraction"] == 7 / 8
    assert result["cost_accounting"]["potentially_unreported_retry_cost_episodes"] == 1
    assert result["latency_by_outcome_ms"]["not_safe_success"]["samples"] == 0
    assert result["latency_by_outcome_ms"]["not_safe_success"]["p95"] is None
    assert result["stage_latency_ms"]["arguments"]["samples"] > 0
    assert result["observed_models"]["planner"] == ["scripted-demo"]


def test_preflight_checks_env_without_disclosing_credentials(monkeypatch):
    monkeypatch.delenv("PREFLIGHT_TEST_KEY", raising=False)
    config = ExperimentConfig(provider=ProviderConfig(kind="openai", model="fixture-model", api_key_env="PREFLIGHT_TEST_KEY"))
    report = check_configuration(config, variants(config, "combined"), 12)
    assert not report["configuration_ready"] and report["network_requests"] == 0
    assert report["planned_episodes"] == 180
    monkeypatch.setenv("PREFLIGHT_TEST_KEY", "PRIVATE_TEST_VALUE")
    report = check_configuration(config, variants(config, "combined"), 12)
    assert report["configuration_ready"]
    assert "PRIVATE_TEST_VALUE" not in json.dumps(report)


async def test_html_data_cannot_close_script_tag(recorded_run, tmp_path):
    from aclab.reporting import write_html
    report = compare_runs([recorded_run], None, tmp_path / "comparison")
    attack = '</script><script src="https://invalid.example/attack"></script>'
    report["records"][0]["model"] = attack
    path = tmp_path / "escaped.html"
    write_html(path, report)
    html = path.read_text()
    assert attack not in html
    assert html.count("</script>") == 2
    encoded = html.split('<script type="application/json" id="data">')[1].split('</script>')[0]
    assert json.loads(encoded)["records"][0]["model"] == attack
    assert "innerHTML" not in html


async def test_failed_aggregation_marks_new_run_incomplete(tmp_path, monkeypatch):
    import aclab.cli as cli
    def fail(*args, **kwargs):
        raise ValueError("aggregation failed")
    monkeypatch.setattr(cli, "summarize", fail)
    directory = tmp_path / "failed"
    args = SimpleNamespace(config="configs/mock.yaml", repeats=1, concurrency=1, dataset=None,
                           tasks=2, matrix="single", max_episodes=5000, output=str(directory))
    with pytest.raises(ValueError, match="aggregation failed"):
        await bench(args)
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["status"] == "incomplete" and manifest["completed_episodes"] == 2
    assert manifest["failure_class"] == "ValueError"
