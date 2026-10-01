# Execution status — completed service-understanding pilot

The corrected model run completed successfully: https://github.com/HarshPopat23/JH-Reliability/actions/runs/36907463064 . Its executed source is `8e79ddec72a63f8bf07c0e2f77d306771e87f8b1`.

Qwen3 4B Instruct and Gemma3 1B each completed 840 scheduled episodes: 24 tasks × seven documentation conditions × five repeats. Twelve tasks per model were held out. Qwen had zero recorded parsing errors; Gemma had twenty (nineteen at the output cap, one incomplete server response). Errors remain in outcome denominators.

Separate post-hoc saved-body audits also completed successfully:

- Native Blaze replay: https://github.com/HarshPopat23/JH-Reliability/actions/runs/36913205724 . Source `cdabfb18eabdb79cdf0fa53d4badb1ceabb7d89f`.
- Live One evaluation/trace/dependency replay: https://github.com/HarshPopat23/JH-Reliability/actions/runs/36914860098 . Source `e1f73c0e40ffb9094bc7218ad2025bf013deed53`.

All 1,660 parsed proposal bodies were checked by both real components. Native and HTTP verdicts agreed with the offline reference. The report distinguishes those replays from actual model-selected executions.

Read `results/service-understanding-final/REPORT.md`. It supersedes the completion interpretation in original per-shard reports, while preserving their strict exact-key scores. The original scorer treats a differing idempotency key as failure even if the desired action completed. Backend-verified completion is a disclosed post-hoc secondary metric, not a pre-registered replacement. This correction does not change source logs or rerun model generations.

The first run 36905170453 failed before any inference episodes; it is excluded. Later report helpers and the digest-pinned One Dockerfile were not the code executed for the corrected model run. Model digests, request hashes, schema hashes and original artifact digests are retained.

Local verification: 106 core tests and ten explicit study/scoring tests passed. Model evidence audit and replay audit passed. Original artifact ZIPs are archived in the repository so evidence does not depend on their thirty-day Actions retention.
