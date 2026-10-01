# JH-Reliability: schema context and native gateway experiment


## Main findings

This run retained 1,680 real model episodes. Each documentation condition has 60 held-out episodes per model (12 tasks × five repeats).

Qwen produced semantically correct bodies in 60/60 rich cases and 60/60 prose cases, versus 0/60 basic-schema cases. It mostly abstained: rich completed 0/60 actions; prose completed 4/60. This supports a benefit from supplied service facts, but does not establish a unique declarative-syntax advantage or reliable task execution.

Gemma completed 18/60 moderate-schema cases, 8/60 rich cases, and 17/60 prose cases. All its successes were export tasks; it failed both conversion families. Richer documentation was not uniformly better for this small model.

Across the seven held-out Gemma conditions, native Blaze reduced failed HTTP service calls from 220 to 22 (90.0% fewer), while completed actions were unchanged. This is request filtering, not model correction, a production traffic forecast, or a model-token cost saving.

Live One registry/version/outage checks and the separate HTTP conformance replay worked. They do not isolate a One-caused model accuracy improvement. Native AlterSchema ran only as a separate probe; it cannot be credited with a model-quality or cache-speed improvement here.

Rich context increased prompt tokens and median inference duration. No end-to-end latency, dollar-cost, energy, or universally safer full-stack improvement is established. Completion scoring was corrected post hoc as disclosed below; raw exact-match scores remain available for audit.

Read the limits before sharing these results. They concern three synthetic service families, not general model intelligence or production reliability.


## Documentation variants

| Variant | Information supplied |
|---|---|
| none | Generic envelope and task; no service-specific unit documentation |
| poor | Basic body fields and types |
| moderate | Authoritative unit enum, version and other assertions, without explanatory semantics |
| rich | OpenAPI 3.1 wrapper, JSON Schema assertions, correct descriptions and examples |
| prose | Similar correct interface facts described in prose; approximate information control |
| false | Deliberately wrong semantic descriptions, while current structural assertions remain correct |
| stale | Coherent previous-version contract and units, conflicting with current task version |

The three authoritative input schemas require resource (string), value (nonnegative integer), unit (family-specific enum), expected_version (const 2), and a nonempty idempotency_key, with additionalProperties false. Refunds use minor currency units; scheduling uses Unix milliseconds; exports use public_only. The shared output schema requires status in done/duplicate and a positive integer version. These simple schemas and backend states are frozen in study.py.

## What ran

Real Qwen3 4B Instruct and Gemma3 1B through pinned Ollama, native Sourcemeta Blaze/AlterSchema, and live Sourcemeta One containers on GitHub-hosted Linux CPUs. Synthetic services for refunds, scheduling and public-only exports. 24 tasks, five repeats, seven documentation variants; twelve tasks for development and twelve held out.

A generic output envelope is constrained during decoding. Service-specific unit enums and version requirements are supplied as context and enforced independently by Blaze. Executed candidates are sent to fresh sandbox states with and without Blaze, with identical backend rules. Abstentions are not executed. No model reconsideration or retry loop is tested.

Scoring disclosure: the frozen primary endpoint requires the exact task-specific idempotency key. During inspection of the first two completed Gemma shards, some actions completed correctly using a different nonempty key. Raw scores and logs are preserved. Backend-verified completion and semantic correctness are disclosed post-hoc secondary endpoints, applied identically to every model and arm; they must not be presented as pre-registered results. Alternate keys are assessed only in fresh per-task sandboxes. Copied example keys remain instruction-fidelity errors and could cause collisions in a shared production journal; this scoring does not establish safe idempotency across operations.

| Model | Documentation | Held-out n | Strict request match | Semantically correct body | Verified completion with Blaze | Failed API calls without Blaze | Blaze input/output rejects | Failed API calls with Blaze | Model errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| gemma3:1b | none | 60 | 0/60 | 0/60 | 0/60 | 60 | 60 | 0 | 0 |
| gemma3:1b | poor | 60 | 0/60 | 0/60 | 0/60 | 60 | 60 | 0 | 0 |
| gemma3:1b | moderate | 60 | 5/60 | 18/60 | 18/60 | 40 | 39 | 1 | 2 |
| gemma3:1b | rich | 60 | 0/60 | 11/60 | 8/60 | 8 | 8 | 0 | 0 |
| gemma3:1b | prose | 60 | 0/60 | 17/60 | 17/60 | 40 | 19 | 21 | 1 |
| gemma3:1b | false | 60 | 0/60 | 6/60 | 1/60 | 3 | 3 | 0 | 1 |
| gemma3:1b | stale | 60 | 0/60 | 0/60 | 0/60 | 9 | 9 | 0 | 2 |
| qwen3:4b-instruct | none | 60 | 0/60 | 0/60 | 0/60 | 0 | 0 | 0 | 0 |
| qwen3:4b-instruct | poor | 60 | 0/60 | 0/60 | 0/60 | 0 | 0 | 0 | 0 |
| qwen3:4b-instruct | moderate | 60 | 0/60 | 18/60 | 0/60 | 0 | 0 | 0 | 0 |
| qwen3:4b-instruct | rich | 60 | 60/60 | 60/60 | 0/60 | 0 | 0 | 0 | 0 |
| qwen3:4b-instruct | prose | 60 | 60/60 | 60/60 | 4/60 | 0 | 0 | 0 | 0 |
| qwen3:4b-instruct | false | 60 | 38/60 | 38/60 | 0/60 | 0 | 0 | 0 | 0 |
| qwen3:4b-instruct | stale | 60 | 0/60 | 0/60 | 0/60 | 0 | 0 | 0 | 0 |

## Paired context effects: frozen strict matching

Differences in percentage points, with 95% bootstrap intervals over matched held-out task clusters. Each model has twelve held-out task clusters; repeated episodes do not count as independent tasks. These are exploratory contrasts; no broad population-level significance or multiplicity-adjusted claim is made.

| Model | Contrast | Difference | 95% interval |
|---|---|---:|---|
| gemma3:1b | rich-poor | 0.0 pp | [0.0, 0.0] pp |
| gemma3:1b | rich-moderate | -8.3 pp | [-25.0, 0.0] pp |
| gemma3:1b | rich-prose | 0.0 pp | [0.0, 0.0] pp |
| gemma3:1b | false-rich | 0.0 pp | [0.0, 0.0] pp |
| gemma3:1b | stale-rich | 0.0 pp | [0.0, 0.0] pp |
| qwen3:4b-instruct | rich-poor | 100.0 pp | [100.0, 100.0] pp |
| qwen3:4b-instruct | rich-moderate | 100.0 pp | [100.0, 100.0] pp |
| qwen3:4b-instruct | rich-prose | 0.0 pp | [0.0, 0.0] pp |
| qwen3:4b-instruct | false-rich | -36.7 pp | [-61.7, -15.0] pp |
| qwen3:4b-instruct | stale-rich | -100.0 pp | [-100.0, -100.0] pp |

## Secondary paired effects: backend-verified completion

Post-hoc completion scoring removes exact idempotency-key matching; it still requires a contract-valid body, correct goal values, HTTP 200, expected response state, and successful native output validation.

| Model | Contrast | Difference | 95% interval |
|---|---|---:|---|
| gemma3:1b | rich-poor | 13.3 pp | [0.0, 30.0] pp |
| gemma3:1b | rich-moderate | -16.7 pp | [-35.0, -3.3] pp |
| gemma3:1b | rich-prose | -15.0 pp | [-35.0, 0.0] pp |
| gemma3:1b | false-rich | -11.7 pp | [-26.7, 0.0] pp |
| gemma3:1b | stale-rich | -13.3 pp | [-30.0, 0.0] pp |
| qwen3:4b-instruct | rich-poor | 0.0 pp | [0.0, 0.0] pp |
| qwen3:4b-instruct | rich-moderate | 0.0 pp | [0.0, 0.0] pp |
| qwen3:4b-instruct | rich-prose | -6.7 pp | [-20.0, 0.0] pp |
| qwen3:4b-instruct | false-rich | 0.0 pp | [0.0, 0.0] pp |
| qwen3:4b-instruct | stale-rich | 0.0 pp | [0.0, 0.0] pp |

## Decision understanding, abstention and semantic failures

Body accuracy scores the proposed request even when action is abstain. Actual completion requires execution. A contract-valid request can still have the wrong amount, timestamp or resource. High confidence is not independently verified confidence.

| Model | Documentation | Semantic accuracy, 95% task-cluster interval | Abstentions | Valid but semantically wrong executions | Non-correct bodies with probability >=0.9 | Exact-key-only mismatches |
|---|---|---|---:|---:|---:|---:|
| gemma3:1b | none | 0.0% [0.0, 0.0] | 0 | 0 | 59 | 0 |
| gemma3:1b | poor | 0.0% [0.0, 0.0] | 0 | 0 | 59 | 0 |
| gemma3:1b | moderate | 30.0% [8.3, 55.0] | 0 | 1 | 32 | 13 |
| gemma3:1b | rich | 18.3% [0.0, 40.0] | 44 | 0 | 36 | 11 |
| gemma3:1b | prose | 28.3% [8.3, 53.3] | 2 | 21 | 36 | 17 |
| gemma3:1b | false | 10.0% [0.0, 28.3] | 55 | 0 | 39 | 6 |
| gemma3:1b | stale | 0.0% [0.0, 0.0] | 49 | 0 | 43 | 0 |
| qwen3:4b-instruct | none | 0.0% [0.0, 0.0] | 60 | 0 | 0 | 0 |
| qwen3:4b-instruct | poor | 0.0% [0.0, 0.0] | 60 | 0 | 0 | 0 |
| qwen3:4b-instruct | moderate | 30.0% [6.7, 55.0] | 60 | 0 | 2 | 18 |
| qwen3:4b-instruct | rich | 100.0% [100.0, 100.0] | 60 | 0 | 0 | 0 |
| qwen3:4b-instruct | prose | 100.0% [100.0, 100.0] | 56 | 0 | 0 | 0 |
| qwen3:4b-instruct | false | 63.3% [38.3, 85.0] | 60 | 0 | 4 | 0 |
| qwen3:4b-instruct | stale | 0.0% [0.0, 0.0] | 60 | 0 | 20 | 0 |

Intervals that collapse to 0% or 100% reflect a small authored sample with no observed within-sample variation; they do not imply certainty for unseen workflows. The same caution applies to bootstrap differences.

## Output budget failures

| Model | Errors | Errors ending at output limit | Incomplete done=false errors | Episodes missing token counters |
|---|---:|---:|---:|---:|
| gemma3:1b | 20 | 19 | 1 | 1 |
| qwen3:4b-instruct | 0 | 0 | 0 | 0 |

All arms use the same 128-token output budget. Budget truncation remains a failure in every task denominator. Token totals include truncated responses where counters exist, even where parsing failed; an incomplete Gemma response lacked counters, so token totals are reported counts rather than a fully known session total. This budget limits interpretation: malformed outputs at the cap do not alone establish intrinsic JSON-generation failure.

## Service-family breakdown

Each cell is semantically correct bodies / verified completed actions / 20 held-out episodes. Gemma successes are limited to export tasks; neither money nor timestamp conversions succeeded. This prevents pooled rates from hiding that weakness.

| Model | Documentation | Refund | Schedule | Export |
|---|---|---|---|---|
| gemma3:1b | none | 0 / 0 / 20 | 0 / 0 / 20 | 0 / 0 / 20 |
| gemma3:1b | poor | 0 / 0 / 20 | 0 / 0 / 20 | 0 / 0 / 20 |
| gemma3:1b | moderate | 0 / 0 / 20 | 0 / 0 / 20 | 18 / 18 / 20 |
| gemma3:1b | rich | 0 / 0 / 20 | 0 / 0 / 20 | 11 / 8 / 20 |
| gemma3:1b | prose | 0 / 0 / 20 | 0 / 0 / 20 | 17 / 17 / 20 |
| gemma3:1b | false | 0 / 0 / 20 | 0 / 0 / 20 | 6 / 1 / 20 |
| gemma3:1b | stale | 0 / 0 / 20 | 0 / 0 / 20 | 0 / 0 / 20 |
| qwen3:4b-instruct | none | 0 / 0 / 20 | 0 / 0 / 20 | 0 / 0 / 20 |
| qwen3:4b-instruct | poor | 0 / 0 / 20 | 0 / 0 / 20 | 0 / 0 / 20 |
| qwen3:4b-instruct | moderate | 0 / 0 / 20 | 0 / 0 / 20 | 18 / 0 / 20 |
| qwen3:4b-instruct | rich | 20 / 0 / 20 | 20 / 0 / 20 | 20 / 0 / 20 |
| qwen3:4b-instruct | prose | 20 / 4 / 20 | 20 / 0 / 20 | 20 / 0 / 20 |
| qwen3:4b-instruct | false | 5 / 0 / 20 | 13 / 0 / 20 | 20 / 0 / 20 |
| qwen3:4b-instruct | stale | 0 / 0 / 20 | 0 / 0 / 20 | 0 / 0 / 20 |

## Latency and token use

Model duration comes from the actual Ollama response and excludes the duplicate gateway execution used by this experiment. Reported episode wall time in raw records includes both layer branches and is not production end-to-end latency. Hosts differ in CPU hardware, so cross-model timing is descriptive rather than a controlled hardware speed comparison.

| Model | Documentation | Median model duration ms | Input tokens | Output tokens |
|---|---|---:|---:|---:|
| gemma3:1b | none | 5004.129404 | 5800 | 3991 |
| gemma3:1b | poor | 6101.751222 | 11620 | 3928 |
| gemma3:1b | moderate | 6363.174623 | 12080 | 4088 |
| gemma3:1b | rich | 9647.600621 | 27560 | 4036 |
| gemma3:1b | prose | 8124.0294175 | 20420 | 4101 |
| gemma3:1b | false | 9812.152163 | 27580 | 4207 |
| gemma3:1b | stale | 4459.482114 | 27100 | 4220 |
| qwen3:4b-instruct | none | 6047.338983 | 5460 | 3889 |
| qwen3:4b-instruct | poor | 6758.8096485 | 10680 | 4068 |
| qwen3:4b-instruct | moderate | 6728.5686445 | 11300 | 3827 |
| qwen3:4b-instruct | rich | 8865.448211 | 26000 | 4884 |
| qwen3:4b-instruct | prose | 7419.63401 | 19820 | 4216 |
| qwen3:4b-instruct | false | 8813.073911 | 25980 | 4817 |
| qwen3:4b-instruct | stale | 7573.311439 | 25500 | 4750 |

## Repeat stability

pass^5 means all five repeated episodes completed safely for a task; it is not pass@5 (any successful attempt).

| Model | Documentation | Strict success all five repeats | Verified completion all five repeats |
|---|---|---:|---:|
| gemma3:1b | none | 0/12 | 0/12 |
| gemma3:1b | poor | 0/12 | 0/12 |
| gemma3:1b | moderate | 1/12 | 3/12 |
| gemma3:1b | rich | 0/12 | 0/12 |
| gemma3:1b | prose | 0/12 | 3/12 |
| gemma3:1b | false | 0/12 | 0/12 |
| gemma3:1b | stale | 0/12 | 0/12 |
| qwen3:4b-instruct | none | 0/12 | 0/12 |
| qwen3:4b-instruct | poor | 0/12 | 0/12 |
| qwen3:4b-instruct | moderate | 0/12 | 0/12 |
| qwen3:4b-instruct | rich | 0/12 | 0/12 |
| qwen3:4b-instruct | prose | 0/12 | 0/12 |
| qwen3:4b-instruct | false | 0/12 | 0/12 |
| qwen3:4b-instruct | stale | 0/12 | 0/12 |

## What Blaze changed

| Model | Actual native calls, all episodes | Median native engine ns | Median IPC wall ns | Held-out completion difference, with minus without |
|---|---:|---:|---:|---:|
| gemma3:1b | 613 | 2565 | 130574 | 0 |
| qwen3:4b-instruct | 16 | 3731.0 | 104142.0 | 0 |

Blaze acceptance/rejection is independently cross-checked against Python Draft 2020-12 validation offline, after inference timing. This checks structural contract validity, not semantic safety.

| Model | Input proposals checked | Correct rejects | False rejects | Correct accepts | False accepts |
|---|---:|---:|---:|---:|---:|
| gemma3:1b | 522 | 379 | 0 | 143 | 0 |
| qwen3:4b-instruct | 8 | 0 | 0 | 8 | 0 |

Blaze does not change the model proposal in this design. A reduction in failed HTTP calls means contract violations were stopped before reaching the service, not that the task was repaired. The backend is deliberately strict and rejects semantic mismatches against executable reference state; therefore zero unsafe writes are strongly determined by backend safeguards, not evidence that schemas guarantee safety.

## Calibration

| Model | Label target | Probability variant | Held-out probability observations | Brier | ECE |
|---|---|---|---:|---:|---:|
| gemma3:1b | strict exact request | raw | 414 | 0.9151 | 0.9480 |
| gemma3:1b | strict exact request | dev_fit_histogram | 414 | 0.0120 | 0.0051 |
| gemma3:1b | semantic body (secondary) | raw | 414 | 0.8070 | 0.8345 |
| gemma3:1b | semantic body (secondary) | dev_fit_histogram | 414 | 0.1098 | 0.0022 |
| qwen3:4b-instruct | strict exact request | raw | 420 | 0.0905 | 0.0789 |
| qwen3:4b-instruct | strict exact request | dev_fit_histogram | 420 | 0.0863 | 0.0386 |
| qwen3:4b-instruct | semantic body (secondary) | raw | 420 | 0.1333 | 0.1218 |
| qwen3:4b-instruct | semantic body (secondary) | dev_fit_histogram | 420 | 0.1191 | 0.0047 |

Raw probabilities are self-reported estimates of proposal correctness. The postprocessor is fitted only on development labels and does not alter model choices. Probability metrics exclude episodes without valid probability output; task-completion denominators still include errors. A global calibration mapping can hide subgroup differences. This pilot does not establish either model as calibrated, and schema validity cannot establish confidence reliability.

Gemma puts all usable held-out probabilities in the top raw bin. Histogram calibration therefore mostly replaces its confidence with a pooled development success rate. Lower ECE from this nearly constant score is not improved decision discrimination; at thresholds above that base rate it rejects every candidate. Threshold observations are retained in detailed-analysis.json.

## One, AlterSchema and backend checks

Live registry probe artifacts: 12. Passed: 12.

One fetches were digest-checked against frozen authoritative input contracts. The model documentation was generated locally; One did not supply the rich OpenAPI descriptions in this study. Four concurrent clients fetched v1, then explicitly switched to v2; outage fetches failed closed and recovery was checked. These tests establish versioned serving and explicit client selection, not automatic discovery of an approval change, auth permissions, or a causal One-on/off model accuracy gain. Versioned contracts were deployed together, without server hot reload.

AlterSchema performed genuine native linter transformations as a separate infrastructure probe. Those transformed schemas were not substituted into model context or the timed gateway validator. Compiled-validator reuse was independently compared with fresh worker startup/compilation: the cold measurement includes process startup and IPC, while the warm measurement includes IPC, parsing and validation. This measures worker reuse, not an AlterSchema-caused speedup, semantic deduplication, model-decision caching, or a reduction in inference calls.

Ownership, consent, state-race and concurrent idempotency probes run independently of model episodes. These fixture checks use a simulated backend; they do not establish resilience of production databases or distributed transactions.

## Limits and exact attribution

- Rich versus poor changes both available facts and documentation length. Some service facts are genuinely unavailable without documentation; this tests usefulness of supplied contracts rather than stronger general reasoning.
- Rich versus matched prose tests presentation with similar facts, but not a standalone JSON Schema versus OpenAPI comparison. Rich uses OpenAPI with JSON Schema bodies; their separate contributions are not identified.
- False documentation deliberately contradicts correct assertions about units; stale documentation describes a prior version. These are robustness conditions, not information-matched richness comparisons.
- Only three authored service families and twelve held-out tasks; no human-reviewed semantic labels, real production services, equal-token control, multi-turn correction loop, or deployment-level calibration claim.
- All model arms share one output envelope. Native unit/version contract checks are stricter than that envelope, allowing actual runtime validation failures.
- In these toy contracts expected_version is a fixed constant aligned with the deployed contract version. This is an authored snapshot constraint, not proof that JSON Schema can query live resource state. A production API should distinguish interface version from resource concurrency version and enforce the latter against backend state.
- Dollar cost and energy savings were not measured. Every retained episode makes one model call; the matched layer comparison adds no model retry. Avoided backend requests are not evidence of reduced model-token costs.
- JSON BinPack is not part of this study. AlterSchema equivalence/canonical hash behavior is not established by the separate transformation probe, and cache savings cannot be attributed to AlterSchema.
- The initial run 36905170453 completed zero episodes after native startup failed. It is excluded from all model comparisons. The corrected source commit is 8e79ddec72a63f8bf07c0e2f77d306771e87f8b1; raw manifests and model digests pin the retained evidence.

Raw evidence: GitHub Actions run https://github.com/HarshPopat23/JH-Reliability/actions/runs/36907463064 . Read audit.json and detailed-analysis.json before drawing conclusions.

## Infrastructure timings and scope

Each row is one independently provisioned job. These are direct component measurements, not full-task speedups.

| Shard/model | One verified fetches | Four-agent refresh/outage/recovery | Warm cached worker median µs | Fresh worker startup + compile + validation median µs | Native AlterSchema CLI median µs |
|---|---:|---|---:|---:|---:|
| gemma3:1b shard 0 | 3 | See corresponding registry-probes.json | 55.60 | 2894.81 | 2338.73 |
| gemma3:1b shard 1 | 3 | See corresponding registry-probes.json | 70.44 | 2693.00 | 2112.99 |
| gemma3:1b shard 2 | 3 | See corresponding registry-probes.json | 83.98 | 3301.81 | 2326.33 |
| gemma3:1b shard 3 | 3 | See corresponding registry-probes.json | 69.77 | 3089.30 | 2260.13 |
| gemma3:1b shard 4 | 3 | See corresponding registry-probes.json | 71.00 | 3490.73 | 2229.98 |
| gemma3:1b shard 5 | 3 | See corresponding registry-probes.json | 69.54 | 2465.23 | 1941.98 |
| qwen3:4b-instruct shard 0 | 3 | See corresponding registry-probes.json | 70.65 | 2990.91 | 2083.16 |
| qwen3:4b-instruct shard 1 | 3 | See corresponding registry-probes.json | 71.70 | 2932.47 | 2394.02 |
| qwen3:4b-instruct shard 2 | 3 | See corresponding registry-probes.json | 96.32 | 2946.84 | 2191.71 |
| qwen3:4b-instruct shard 3 | 3 | See corresponding registry-probes.json | 44.84 | 2307.64 | 1774.55 |
| qwen3:4b-instruct shard 4 | 3 | See corresponding registry-probes.json | 69.28 | 2954.61 | 2103.22 |
| qwen3:4b-instruct shard 5 | 3 | See corresponding registry-probes.json | 32.13 | 2262.23 | 1752.85 |

Native output-contract negative controls also rejected the malformed response {"acknowledged": true} for all three service families before timed episodes; the worker source contains those asserted live checks. The backend probe named unexpected_response_python_control is a separate Python-only control and is not a native measurement. Runtime native-call counts above exclude setup controls and cache microbenchmarks.

## Post-hoc native and live One replay

Qwen abstentions never reach the timed gateway. To test conformance of its real generated bodies, every saved body was evaluated again in a separately built native Blaze worker and over real HTTP in an actual One container. No new inference, task execution or retry occurred. This is post-hoc contract evidence, not a repaired task-completion score.

| Model | Saved bodies | Native rejects | One HTTP rejects | Offline reference disagreements | Native engine median µs | Native IPC median µs | One HTTP p50 / p95 / p99 ms, concurrency 8 |
|---|---:|---:|---:|---:|---:|---:|---|
| gemma3:1b | 820 | 634 | 634 | 0 | 0.110 | 74.254 | 15.072 / 40.016 / 50.117 |
| qwen3:4b-instruct | 840 | 372 | 372 | 0 | 0.952 | 102.853 | 9.637 / 39.193 / 40.446 |

One also returned actual detailed traces for three valid and three invalid-unit fixtures, and three dependency responses. HTTP timings include client serialization, transport and service processing under eight concurrent clients; native IPC uses a serialized worker on another host. They are not a matched native-engine versus HTTP speed comparison.

Native replay: https://github.com/HarshPopat23/JH-Reliability/actions/runs/36913205724 . Live One replay: https://github.com/HarshPopat23/JH-Reliability/actions/runs/36914860098 . Their immutable source commits differ from the original model run; see provenance below and raw artifact manifests.

## What remains to establish

1. Diagnose Qwen action abstention with explicit action instructions and counterbalanced enum/prompt controls. Keep proposed-body accuracy separate from execution.
2. Pre-register separate semantic completion and idempotency-instruction metrics, require complete Ollama responses, and rerun all matched conditions with a sufficient common output budget.
3. Add independently reviewed real or realistic services, unseen service families, more held-out tasks, and equal-fact/equal-token controls separating JSON Schema, OpenAPI and prose.
4. Retrieve actual model-facing descriptions from One, change an approved version while agents run, and test application refresh/TTL behavior against pinned and stale clients.
5. Compare no retry, generic validation feedback and detailed trace feedback with matched maximum model attempts and unchanged backend safeguards.
6. Test worker pools and 50+ concurrent requests; the current native bridge serializes calls, while One HTTP replay used eight concurrent clients.
7. Preserve transformed schemas and test validation equivalence over diverse instances before attributing cache benefits to AlterSchema. Validator-cache keys may ignore non-validating annotations only when safe for that consumer; model-context caches must include descriptions/examples, versions, model settings and relevant state.
8. Measure inference/backend/registry costs and energy explicitly. A constant calibrated base-rate estimate is not a useful semantic judge or a guarantee against confident wrong decisions.

## Provenance

- Model experiment: 8e79ddec72a63f8bf07c0e2f77d306771e87f8b1, run 36907463064.
- Native replay: cdabfb18eabdb79cdf0fa53d4badb1ceabb7d89f, run 36913205724.
- One HTTP replay: e1f73c0e40ffb9094bc7218ad2025bf013deed53, run 36914860098.
- Blaze source: 059dbed08ea26bd9a630bad5eb07421f4cc34cc0. Ollama: 0.32.0. Both models: Q4_K_M.
- Observed official One 6.7 image digest: sha256:0a68085e2842b461d06518c145a209132b4fbcdb9ef76088645466787f22ba8f. The follow-up Dockerfile pins this digest for reproduction; the executed model source used the tag.
- Exact model digests, request/document hashes, schemas and native binary hashes are in the raw artifacts and audited analysis.

The [evidence archive](evidence.zip) preserves the original fifteen GitHub artifact ZIPs, with their GitHub SHA-256 digests in INDEX.json. [audit.json](audit.json) and [replay-audit.json](replay-audit.json) passed. [detailed-analysis.json](detailed-analysis.json) contains the full metrics and calibration observations. Rebuild this report with python experiments/service-understanding/reproduce_report.py after installing the project.
