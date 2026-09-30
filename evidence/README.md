# Included engineering evidence

All included episodes use the scripted mock planner. No paid or local learned model was benchmarked. The figures below verify the pipeline's intended behavior; they are not effect sizes for GPT, Claude, Gemini, Llama, or Jev.

The combined study uses 72 synthetic task IDs × 5 repeats × 5 variants = **1,800 episodes**. Every variant has 360 episodes.

| Variant | Safe completion | Disallowed mutations |
|---|---:|---:|
| Baseline | 54.17% | 165 |
| Rich descriptions | 54.17% | 165 |
| Schema gate | 54.17% | 165 |
| Deterministic policy | 70.83% | 90 |
| Full pipeline with scripted intent checks | 95.83% | 0 |

The planner deliberately ignores description enrichment. The equal documentation scores are expected and prevent a false claim that mock behavior establishes better model understanding. The full pipeline's remaining failures are partial-update cases; it stops for review without pretending that an uncertain operation completed. Zero disallowed mutations in these authored fixtures is not a universal safety guarantee.

Additional evidence:

- **106 passing tests**, including malformed arguments, trusted authority/approval binding, schema drift, provider fixtures, semantic failure, cache dependencies/cancellation, duplicate execution, stale state, lost responses, partial changes, valid replies without live effects, resource-content injection, and API admission checks.
- **432 cache-study episodes**: unchanged safe completion across cache off/on; cache hits and stage timings are in the summary/traces.
- **60 documentation-study episodes**: identical behavior with fixed enforcement, as intended for the mock planner.
- **12 semantic development examples**: the scripted evaluator has 75% label accuracy. Its failures demonstrate why a rule checker is not automatically a good semantic evaluator. This tiny authored set cannot calibrate deployment risk.
- **120 real localhost HTTP requests at concurrency 8**, all HTTP 200. See `v02/local-load.json` for measured latency and throughput. These are mock-gateway measurements on one machine, not real-model or distributed-system capacity.
- The project installs through its editable package, passes `pip check`, builds a wheel, and the separately installed release wheel loads the matching catalog and passes close/injection fixtures.

Each study folder contains frozen contracts, configuration/data/implementation hashes, explicit completion status, raw episodes, CSV, statistics, paired task-cluster intervals, and a readable report. All bundled studies were refreshed for v0.2's stricter safe-completion scoring.

The studies are under `v02/`. The offline browser report in `v02/comparison/report.html` displays the main and cache studies. Four main-study comparisons are eligible against its baseline; two cache arms are flagged because their repeat counts differ. This deliberately demonstrates the control checks. `v02/html-check.json` records jsdom integration checks for search, evidence filters, sorting, details rendering, and zero external requests. Headless Chromium download was unavailable; real-browser rendering/layout and native details expansion remain unverified. These interface checks do not validate real-model effectiveness. Mock token/evaluator/infrastructure rates are explicitly zero demonstration assumptions; these do not establish production savings. Live profiles leave unknown costs null until rates are supplied.

`verification.json` records current source hashes and test status. After installing the repo, run:

```bash
python scripts/verify_evidence.py
```

That recomputes the summaries, checks hashes, and checks complete coverage of task/repeat/variant combinations without calling a model. It verifies internal consistency, not authenticity or commercial worth. Docker/One, Redis, real provider accounts, unseen APIs, production identity, and durable distributed execution remain unverified.
