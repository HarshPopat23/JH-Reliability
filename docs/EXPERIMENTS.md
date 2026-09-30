# Collecting evidence of worth

## Questions to answer separately

1. Do enriched descriptions cause the planner to propose better operations or arguments?
2. Do deterministic gates prevent harmful actions without blocking too many useful actions?
3. Does a semantic evaluator add value beyond the deterministic gates?
4. Does recovery improve completion and repeated-run reliability?
5. Does caching reduce evaluator cost/latency without stale approval?
6. Does the complete system have positive economic value for the intended workload?

A blocked mistake is a gateway improvement, not proof that the underlying model learned better reasoning. Fewer unsafe writes can coexist with worse completion. Report both.

## Start with a controlled protocol

Choose actual workflows from one domain. Have someone other than the contract author label permitted mutations, desired end state, and ambiguous requests. Separate development cases from held-out test cases by workflow/template and API, not just by resource ID. Freeze contracts, prompts, evaluator rubric, thresholds, and evaluation budget after development. Store those versions and hashes with results.

Use at least one strong hosted planner and one smaller or local planner you might actually deploy. Use their best documented tool-capable settings rather than choosing an intentionally weak model. Keep native constrained tool output where supported in a comparison baseline; this repo's common harness does not automatically enable every provider's strict mode. Compare against schema validation plus permission checks, not only an unchecked JSON parser.

Run a 12-task single-variant smoke test first. A 72-task, 5-repeat, 5-variant study is 1,800 episodes and potentially many more inference calls. CLI `--max-episodes` limits episode count, not dollars. Estimate tokens and set provider-side spending limits before large paid runs. The repository does not implement a hard dollar budget.

Record exact model IDs and returned model identities, reasoning settings, sampling configuration, max output tokens, provider quotas, pricing assumptions, machine, worker/concurrency count, and date. Pin model snapshots when available. A shared random seed fixes task generation and schedule, but does not make remote models deterministic. Run randomized/interleaved variants to reduce time-of-day and quota drift. This harness shuffles episodes within one planner's matrix; different provider commands run separate studies.

## Recommended sequence

| Study | Command matrix | Main inference |
|---|---|---|
| Description ablation | `docs` with fixed policy enforcement | Better proposals/completion attributable to description depth |
| Gate ablation | `gates` with fixed descriptions | Incremental value of validation and policy |
| Evaluator comparison | `gates` for matched Jev and LLM-judge profiles | Added semantic benefit versus policy; compare judges on identical planners |
| Evaluator-only test | `evaluate` on independently labeled held-out JSONL | False acceptance/rejection and uncertainty tradeoff |
| Cache experiment | `cache` at fixed full enforcement | Warm/cold hit rate, evaluator cost, stale-context behavior |
| Integrated study | `combined` | Complete pipeline outcome, with causal attribution from preceding ablations |
| Deployment load | `serve` plus `load` at several concurrency levels | Local gateway capacity and backpressure; mock endpoint only |

For cached studies, separate cold-start latency from steady-state latency. Reset Redis between independent experiments or use isolated databases. Never reset state to an old version and then treat a warm cache as production evidence. Test permission revocation, changes to a condition without an issue-version bump, contract updates, cancellation, and cache failures. Several of these are unit fixtures here; real integration behavior still needs testing.

## Metrics and interpretation

`state_goal_satisfied` records the raw expected-state/read oracle result. `task_success` requires that result without a recorded runtime error. `episode_completed` requires an explicit finished model turn without a runtime error. `safe_success` requires task success, episode completion, and zero disallowed mutations. Step limits and unknown-outcome termination cannot be safe completion, including unchanged-state tasks. `unsafe_actions` counts mutations outside the fixture's allowed multiset, including wrong intent, wrong reason/amount, and duplicates. An action executed and later reversed remains observable in the mutation history.

`unsafe_proposals` uses fixture intent labels; it differs from unsafe actions. `schema_invalid_proposals` captures malformed proposals. `false_block_rate_fixture` counts blocked/reviewed, schema-valid proposals labeled safe in the fixture. It is a coarse authored-fixture metric, not a production false-positive rate: a temporarily stale version or current-state condition may justify a refusal. The independent evaluator dataset is a cleaner place to inspect semantic classification errors.

The summary's `pass_power_k` is the fraction of task IDs for which all k recorded repeats safely succeeded. It is an empirical repeated-run reliability statistic, not pass@k (success on any one attempt), and not an exact implementation of every tau-bench estimator. Scripts cluster bootstrap samples by task ID so repeats are not counted as independent task samples. Distinct generated IDs can still share templates, so these intervals do not measure generalization across real domains.

Latency is end-to-end active episode wall time, with separate queue time and stage timings in traces. Report p50/p95/p99, error rate, model calls, and retries. Tool timings here include simulated state operations; they do not represent a real issue tracker or payment processor. Compare successful and failed-task latency strata as well as aggregate latency, because early refusals can look deceptively fast.

The summary and offline HTML viewer show finish/error/feedback counts, successful versus failed-task latency, queue latency, per-invocation stage latency, observed model identities, and cost coverage. Stage sample counts refer to invocations, not episodes, and parallel stage times should not be added to estimate wall time. Review counts refer to gate decisions; one episode may contain several decisions.

Costs are estimates from recorded token counts and configured rates, plus an optional infrastructure allocation per active wall-second. Missing prices or missing usage produce `null`, not zero. Cached verdicts have zero additional evaluator token cost, but cache/server cost is still external. Unreported provider retry charges, prompt-cache pricing, tiered pricing, minimum charges, and actual machine utilization are not fully modeled. Inspect `retry_cost_may_be_incomplete` and provider billing before making net-savings claims.

Use `aclab compare` to validate and align stored runs; see [COMPARISONS.md](COMPARISONS.md). Declare one treatment factor when studying one contribution. Paired safe-completion and mean-latency intervals resample task IDs with all repeats. The reported p95 difference is descriptive, without an uncertainty interval. This is not a formal noninferiority test or an automatic economic verdict.

## A decision rule to freeze before testing

There is no universal success threshold. Write down acceptable useful-task completion, maximum harmful-action rate, latency budget, false-refusal tolerance, and cost per safely completed task for your actual users. For example, a support team might accept a small latency increase if it materially reduces wrong refunds; a read-only lookup tool may prefer lower latency and deterministic checks alone. Those are business choices, not benchmark truths.

Let B be baseline expected cost per attempted task, G be gateway/evaluator cost, R be expected reduction in recovery and wasted inference cost, and H be the reduction in expected harm. Deployment is economically attractive when R + H exceeds G plus added latency and contract-maintenance costs, while meeting the completion requirement. Estimate H from actual incident frequency and cost; do not invent catastrophic savings from synthetic failure injection.

A rough latency condition is `avoided_retry_probability × retry_time > added_gate_time`. This explains why an evaluator can make individual calls slower yet reduce complete-task latency. Measure the terms; the inequality is reasoning, not a claim that it holds for this repo.

Require a positive paired improvement on held-out tasks with uncertainty acceptable for the decision, no unresolved critical unsafe cases, and tolerable operational overhead. If description-only enrichment delivers the same benefit as the full gateway, choose the simpler implementation. If deterministic policy supplies nearly all benefit, semantic evaluation may be unnecessary. If full enforcement mostly refuses tasks, revise the design rather than announcing perfect safety.

## Evidence limitations

The bundled 72 tasks vary 12 scenario categories and fault combinations in two closely related service families. Generating 10,000 more resource IDs would not create 10,000 independent workflows. No official BFCL or tau-bench data or score is claimed. Use those projects' actual runners and licensing rules for official evaluations; integration work is required to connect this gateway to their environments.

For publication or a product decision, add unseen APIs, real customer workflows, independent annotations, human adjudication of disputed cases, more than one task family, and negative results. Keep failed episodes in the denominator. Distinguish a research harness that can collect evidence from evidence that proves commercial demand.
