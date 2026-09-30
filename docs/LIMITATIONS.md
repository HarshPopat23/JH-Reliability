# What has and has not been demonstrated

The verification record in `evidence/verification.json` is the authoritative list of local checks. Included episode runs use scripted agents/evaluators. Live provider request/response normalization is tested against HTTP fixtures, not paid accounts. Docker/One and Redis were not available for an end-to-end service test. Python 3.12 was tested locally; other CI versions are configured, not already verified remotely.

The offline viewer's search, filters, sorting, and details rendering are checked in jsdom. A headless Chromium download was unavailable, so visual layout, native details expansion, and real-browser compatibility were not verified locally.

## Scientific limits

- The dataset has synthetic issue/order tasks. It is not official BFCL, tau-bench, an unseen-API benchmark, or a validated security benchmark.
- Generated task IDs share templates. Task-cluster intervals do not eliminate template-level dependence.
- Labels and scoring check actions/state, not whether the final natural-language answer is helpful, honest, or complete. There is no interactive human/user simulator.
- The scripted planner ignores enriched descriptions by design. Mock comparisons cannot establish documentation benefits or rank real models.
- The semantic development set is deliberately small. Its threshold sweep is diagnostic, not calibrated production risk.
- Fresh planning requests contain a normalized transcript. Native provider continuation, native tool-result messages, Gemini thought signatures, prompt caching, and provider-specific strict modes are not fully implemented. This is a common harness comparison, not each model's maximum capability.
- Live API costs need manually supplied rates; hidden retry charges and some caching/tier billing can be omitted. Infrastructure allocation is a configured estimate.
- Variant interleaving is within one benchmark process. Provider comparisons across separate runs need additional control of load, model updates, and pricing.
- Offline comparisons reject mismatched controls and incomplete coverage, but matching recorded settings cannot establish equal provider load, machine contention, or billing. The default declared treatment set permits several factors; narrow `--vary` for causal ablations. Paired intervals are descriptive task-cluster bootstrap intervals, not a formal noninferiority decision. p95 differences have no uncertainty interval here.

## Runtime limits

- Every business action is simulated. No GitHub/Jira/payment service connector is supplied. The gateway is not a transparent proxy for arbitrary external APIs.
- State and idempotency records are in memory per episode. Process crashes, worker restarts, and distributed writes need durable service support.
- Approval records are exact-action fixture bindings. There is no real approval UI, expiry/revocation database, OIDC identity mapping, or organization role-management service.
- Business guards are atomic only within the simulated service lock. External services require their own atomic version/condition enforcement.
- No automatic rollback or compensation is claimed. `OUTCOME_UNKNOWN` can stop with a partial change already present.
- Review is a returned state, not a human-review queue. API clients cannot submit arbitrary actor/approval objects.
- Redis caching is optional and trusted; cached payloads are not signed. Singleflight is process-local and TTL is not permission revalidation.
- Catalog hashes detect content differences but do not authenticate publisher provenance. There is no signature verification or universal policy-package sandbox.
- One content pinning assumes an immutable indexed registry during a run. The exact server-assigned root `$id` can be normalized for self-contained schemas; all constraints remain pinned. Its configured canonical URL must match `one_url`. HTTP outage or unexpected schema serialization stops that run; no silent local fallback is used.
- API authentication is one shared bearer key. CLI non-loopback guards can be bypassed by launching uvicorn directly; deployment policy remains your responsibility.
- There is no hard inference dollar cap, global tenant quota, distributed rate limiter, durable job queue, resumable benchmark scheduler, or comprehensive telemetry service.
- Benchmark schedules/results remain O(episodes) memory even though active futures are bounded. The load generator reports latency/status, not CPU, RAM, or network saturation.
- Comparison inputs have a configurable per-file byte limit (128 MiB by default), but parsed records and aggregation remain in memory. Raise the limit only when adequate memory is available; this is not a streaming data warehouse.
- Completed manifests and raw hashes detect incomplete or changed artifacts. They do not provide resumability, cryptographic signatures, provenance authentication, or tamper-proof audit logs.

## Claims to defer

Do not claim “all models improve,” “zero hallucinations,” “exactly once everywhere,” “production ready,” “lower inference latency,” “Jev beats LLM judges,” or “Blaze makes the whole agent faster” from the included checks. Those are hypotheses requiring measured workloads and appropriately strong baselines.

The current useful deliverable is a runnable implementation of the chart with reproducible traces, controlled ablations, and explicit failure behavior. A product decision should follow held-out real-model and real-domain evidence.
