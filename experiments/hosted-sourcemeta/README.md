# Real component pilot

Runs genuine pinned Sourcemeta Blaze, its AlterSchema Linter, JSON BinPack, One 6.7 container, and Ollama 0.32.0 with qwen3:4b-instruct. GitHub Actions uses a standard public-repository CPU runner; no paid API or GPU runner.

8 arms, 12 matched authored tasks, 1 repeat: baseline, schema/Python, policy/Python, policy/native Blaze, policy/One-fetch-local-Blaze, policy/One-HTTP-evaluation, policy/AlterSchema-local-Blaze, full/One-pin-verified-AlterSchema-Blaze-real-Qwen-judge. Randomized arm order per task. All use the same planner settings and documentation. Native calls include identity and engine/IPC/gateway timings. Semantic judge is Qwen, not Jev.

Baseline retains target service authorization, approval, optimistic concurrency, and idempotency. This tests optional gateway gates, not an unsecured target. All target actions are isolated fixtures, never production services.

Kernel validation excludes parsing, serialization, IPC, and diagnostic output. Python and Blaze boolean checks use repeated consumed checksums. One evaluation/trace is exhaustive and does more work; compare separately. Compilation/startup excluded from warm episodes and separately recorded. Registry fetch/validation verifies pinned schema identity before local execution. One outage and locally pinned contract mismatch are tested with fail-closed behavior.

AlterSchema transforms JSON Schemas using genuine Linter. It does not canonicalize arbitrary state; hash identity here is deterministic JSON SHA-256 and is not proof of universal semantic equivalence. BinPack compiles schema and encodes/decodes actual instances. 1,000 round trips per valid case must compare equal. Storage savings do not prove inference savings.

Results are a small CPU pilot, not a production scalability result or a replicated model study. Complete run: 96 episodes, <=800 local inference requests. Missing/failed components stay failed, never fall back to mocks or Python. Partial evidence is uploaded on setup failure too. API monetary cost is zero but infrastructure/electricity cost remains unknown. See manifest and raw episodes before sharing speedup claims.
