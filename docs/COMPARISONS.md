# Comparing models and gateway designs

`aclab compare` reads stored results and performs no inference. It produces `comparison.json` and a self-contained `report.html`. Open the HTML file locally; search, filter evidence types, sort the table, and expand a variant or comparison to inspect accounting and controls. No server or internet connection is needed to view it.

## Choose the question first

| Question | Declared treatment | Keep fixed |
|---|---|---|
| Do descriptions help? | `--vary docs` | Planner, enforcement, evaluator, budgets, concurrency |
| Which checks add value? | `--vary enforcement` | Planner, descriptions, evaluator, budgets, concurrency |
| Which planner works best in this harness? | `--vary provider` | Dataset, descriptions, enforcement, evaluator, repeat/step budgets, concurrency |
| Does Jev beat an LLM evaluator? | `--vary evaluator` | Same planner and all other settings |
| Does semantic caching help? | `--vary cache` | Planner, evaluator, enforcement, descriptions, budgets, concurrency |
| Local versus One validation? | `--vary validator` | Same contract content and all other settings |

All comparisons require identical dataset, contract content, scoring version, implementation fingerprint, and task/repeat coverage. Any differing configuration field outside the declared treatment is reported as a control difference. Defaults permit provider, descriptions, enforcement, evaluator, and cache together, which is useful for an integrated overview. Narrow the factors to answer a causal question. `--vary` with no factors requires every setting to match.

The zero-based baseline selector is `RUN_INDEX:VARIANT`. Variant names come from each run's `manifest.json`: `single` for single runs; `baseline`, `semantics`, `counterexamples`, `workflows`, `recovery` for docs; `baseline`, `schema`, `policy`, `full` for gates (full requires an evaluator); `cache-off`, `cache-on` for cache.

## Worked local example

```bash
aclab preflight --config configs/mock.yaml --matrix docs --tasks 12 --repeats 3
aclab bench --config configs/mock.yaml --matrix docs --tasks 12 --repeats 3 --concurrency 2 --output results/docs-test
aclab compare results/docs-test --baseline 0:baseline --vary docs --output results/docs-view
```

Open `results/docs-view/report.html`. Equal scripted documentation results are expected: the mock planner does not read description enrichment.

## Match real-model runs

Copy profiles and explicitly match non-treatment fields; supplied example profiles are starting points, not a guarantee of a controlled comparison. Use the same frozen dataset, repeat count, step budget, concurrency, descriptions, gate level, and evaluator. Exact provider/model IDs and returned model identities appear in evidence. Set prices and infrastructure assumptions before interpreting cost.

```bash
# After editing the two profiles to match all non-provider fields:
aclab bench --config configs/openai.yaml --matrix gates --tasks 72 --repeats 5 --concurrency 2 --output results/gpt
aclab bench --config configs/anthropic.yaml --matrix gates --tasks 72 --repeats 5 --concurrency 2 --output results/claude
aclab compare results/gpt results/claude --baseline 0:policy --vary provider --output results/models-view
```

Only corresponding policy arms are eligible against that policy baseline when enforcement is held fixed. Other gate arms remain visible with incompatibility reasons. For Jev versus an LLM judge, use profiles with the same planner and compare their full arms with `--vary evaluator`; an evaluator-only `aclab evaluate` study answers a different question about label classification.

A common task seed and paired task IDs do not make remote inference deterministic. Separate commands run at different times. Repeat studies in alternating order, control host load, pin model snapshots when possible, and record provider quotas. Do not compare maximum model capability using this normalized transcript harness alone.

## Read the numbers carefully

- **Safe completion:** correct state/read result, no disallowed mutations, no runtime error, and an explicit finished model turn. Step limits and unknown outcomes are failures. State goals reached before an unfinished termination are reported separately.
- **Latency:** active episode p50/p95/p99, plus successful/unsuccessful strata, queue time, and per-invocation stage distributions. Fast failures can lower aggregate latency. Each stratum can have a different task mix, so neither is a standalone causal estimate.
- **Costs:** known-cost coverage and known subtotals accompany nullable total and cost-per-safe-success estimates. Missing usage/rates stay unknown. Potentially unreported retry costs suppress paired cost differences. Even complete configured estimates are not provider invoices or evidence of production savings.
- **Paired effects:** candidate minus baseline. Safe-completion and mean-latency intervals use a 2,000-draw task-cluster bootstrap, retaining all repeats per task. p95 differences are descriptive and have no interval here. These calculations do not implement a formal noninferiority test, adjust for many comparisons, or establish domain generalization.
- **Failures and reviews:** counts distinguish termination, errors, gate decisions, and feedback. A review is a decision, not a completed human adjudication; one episode can have multiple reviews.

The comparator rejects unfinished artifacts, altered episode bytes, altered frozen datasets/contracts, duplicates, missing coverage, contradictory completion labels, nonfinite main metrics, and mismatched row settings. Summaries are recomputed from raw episodes. A completed manifest and matching hashes establish internal consistency; an author can still forge both. They are not provenance authentication.

Inputs default to a 128 MiB per-file limit. `--max-evidence-mb` can change it, but parsed records and statistics remain in memory. Large-scale collection needs a durable scheduler and external analytical storage. Old v0.1 manifests can be inspected with warnings, but lack the frozen implementation/completion evidence required for current paired comparisons.

Use [EXPERIMENTS.md](EXPERIMENTS.md) to freeze a workload-specific decision rule before testing. The viewer is evidence inspection, not an automatic declaration that a model or product is worth deploying.
