# Agent Contract Lab

A local experiment repository for the question: **do better tool contracts and a checked execution gateway improve safe task completion enough to justify their latency, cost, and maintenance?**

It implements the supplied chart: validate a proposed call, check live state, optionally evaluate intent, enforce trusted permissions and exact-action approval, execute with version and retry controls, verify the outcome, and return structured feedback. All tool actions operate on an isolated simulated issue/order service. Model inference can use real providers.

This is a research prototype and benchmark harness. It does not establish that the idea improves GPT, Claude, Gemini, or Llama. The included evidence uses scripted mock agents; run the live profiles to collect that evidence. Read [the honest assessment](docs/RESEARCH.md), [experiment protocol](docs/EXPERIMENTS.md), and [limitations](docs/LIMITATIONS.md).

## Quick start

Python 3.11+ is required; Python 3.12 is the locally verified version. Run commands from this repository directory.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest -q
aclab demo --category close
aclab bench --config configs/mock.yaml --matrix combined --tasks 72 --repeats 5 --output results/my-mock
```

Windows PowerShell activation: `.venv\Scripts\Activate.ps1`. If activation is unavailable, invoke `.venv\Scripts\python.exe` and `.venv\Scripts\aclab.exe` directly. On Unix, use `.venv/bin/python` and `.venv/bin/aclab` directly.

For the exact dependency versions used for included evidence, install `requirements-lock.txt` before the editable package. Dependencies require an internet connection on first installation; mock experiments then run without model access.

```bash
python -m pip install -r requirements-lock.txt
python -m pip install --no-deps -e .
```

Each output directory must be new. The benchmark writes `manifest.json`, frozen `contracts.json`, `tasks.jsonl`, `episodes.jsonl`, `episodes.csv`, `summary.json`, and a readable `report.md`. JSONL contains proposals, gate decisions, stage timings, usage, and independently scored final state. The manifest records exact configurations, dependency versions, dataset/contract hashes, an implementation fingerprint, scoring version, and evidence type. A run is marked completed only after its reports are written; interrupted or failed runs cannot enter paired comparisons.

To check the included evidence against this source and recompute its statistics without inference, run `python scripts/verify_evidence.py` after installation.

## Test real models

Copy `.env.example` to `.env`, enter your own keys and exact model IDs, and run the appropriate profile. Model names are deliberately not hard-coded because availability changes. These commands send inference requests to your selected provider and can incur charges.

| Provider | Profile | Environment variables | Interface |
|---|---|---|---|
| GPT/OpenAI | `configs/openai.yaml` | `OPENAI_API_KEY`, `OPENAI_MODEL` | Chat Completions tool calling |
| Claude/Anthropic | `configs/anthropic.yaml` | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Messages API tool use |
| Gemini/Google | `configs/gemini.yaml` | `GEMINI_API_KEY`, `GEMINI_MODEL` | Native generateContent function calling |
| Ollama, including supported Llama models | `configs/ollama.yaml` | `OLLAMA_MODEL` | Local `/api/chat`; start Ollama and pull your chosen model first |
| vLLM, LM Studio, or another compatible server | `configs/compatible.yaml` | `COMPATIBLE_BASE_URL`, `COMPATIBLE_MODEL`, optional `COMPATIBLE_API_KEY` | OpenAI-compatible Chat Completions |
| OpenAI planner + Jev evaluator | `configs/jev.yaml` | OpenAI variables + `TYPESAFE_API_KEY`, `JEV_MODEL` | Jev Choice evaluation of proposed mutations |
| Ollama planner + OpenAI judge | `configs/llm-judge.yaml` | `OLLAMA_MODEL`, `OPENAI_API_KEY`, `JUDGE_MODEL` | Separate LLM semantic judge |

Jev is integrated as an evaluator, rather than a general conversation planner. Unidentified names such as “laya” or “lla” can use the compatible profile if their actual server supports that protocol. There is no invented adapter for an unknown API.

Start with a small smoke run, then increase the sample size:

```bash
aclab preflight --config configs/openai.yaml --matrix single --tasks 12 --repeats 1
aclab bench --config configs/openai.yaml --matrix single --tasks 12 --repeats 1 --concurrency 1 --output results/openai-smoke
aclab bench --config configs/openai.yaml --matrix docs --tasks 72 --repeats 5 --output results/openai-docs
aclab bench --config configs/openai.yaml --matrix gates --tasks 72 --repeats 5 --output results/openai-gates
aclab bench --config configs/jev.yaml --matrix gates --tasks 72 --repeats 5 --output results/openai-jev-gates
```

`preflight` compiles the contracts and checks configuration, required environment-variable presence, episode count, pricing readiness, and external dependencies without network requests. It cannot confirm credentials, endpoint availability, model access, or affordability. It does not print credential values.

Swap the profile to test other planners. To compare Jev with an LLM judge, keep the planner, tasks, descriptions, budgets, concurrency, and gate level identical. Copy and edit YAML profiles to make that controlled comparison; the supplied LLM-judge example uses a different planner for convenience.

Providers use native tool declarations but each planning step receives a fresh request containing a common normalized transcript. This makes the harness consistent across adapters; it does not reproduce each vendor's most optimized native multi-turn agent loop. `provider.mode: json` is available for models without tool calling. Treat tools and JSON mode as separate conditions.

## Compare evidence and open the interactive report

```bash
# A documentation ablation, with enforcement held constant:
aclab compare results/openai-docs --baseline 0:baseline --vary docs --output results/docs-comparison
# View the included mock studies, with mismatched repeat counts flagged:
aclab compare evidence/v02/mock-combined evidence/v02/mock-cache --baseline 0:baseline --output results/bundled-comparison
```

Open the output `report.html` directly in your browser. It works offline, with search, evidence filtering, sorting, latency breakdowns, cost coverage, and paired effects. The included example is `evidence/v02/comparison/report.html`.

For different model runs, supply both directories and `--vary provider`. For matched Jev versus LLM evaluator runs, use `--vary evaluator`. Keep datasets, repeat counts, concurrency, descriptions, enforcement, and all other settings matched. `--vary` declares the experimental treatment; it does not fix differences in real provider load or hardware. The command validates raw hashes, frozen contracts, completion status, settings and complete coverage, recomputes summaries, and refuses paired statistics when controls differ. Read [the comparison guide](docs/COMPARISONS.md) before interpreting rankings.

Safe completion in v0.2 requires a finished model turn, correct state/read outcomes, and no disallowed mutations. Step-budget exhaustion, errors, and unknown outcomes remain failures even if the state goal was reached. Old v0.1 evidence is viewable with warnings but cannot be paired with this scoring version.

## What the matrices isolate

| Matrix | Changed factor | Held constant |
|---|---|---|
| `docs` | Basic description → intent/effects → counterexamples → workflow → recovery | Configured enforcement and evaluator |
| `gates` | Baseline → schema → policy → full semantic evaluation, if configured | Configured descriptions, planner, tasks |
| `cache` | Semantic cache off/on | Planner, evaluator, descriptions, enforcement |
| `combined` | An end-to-end progression | Tasks and planner; several factors change |
| `single` | One exact configuration | Everything |

All arms retain target authorization, exact-action approval, primitive argument checks, atomic version comparison, and target deduplication. The baseline is useful and protected; it is not designed to be a helpless agent. The mock planner ignores description enrichment, so mock documentation variants should show no improvement.

## Independent evaluator benchmark

```bash
aclab evaluate --config configs/mock.yaml --output results/eval-mock
aclab evaluate --config configs/jev-evaluator.yaml --output results/eval-jev
aclab evaluate --config configs/llm-judge.yaml --output results/eval-llm
```

The 12 authored examples in `datasets/semantic-dev.jsonl` exercise intent, target, amount, conditions, ambiguity, and untrusted content. Outputs include a confusion matrix and confidence-threshold sweep. These are development fixtures. Create a larger independently labeled dataset, split development/test sets, and freeze thresholds before evaluating held-out examples. Self-reported confidence is not calibrated safety probability.

## Local API and load testing

```bash
aclab serve --host 127.0.0.1 --port 8000
# In another terminal with the environment activated:
aclab load --url http://127.0.0.1:8000 --requests 120 --concurrency 8 --output results/local-load.json
```

FastAPI docs: `http://127.0.0.1:8000/docs`. `POST /run` accepts only `{"task_index": 1, "profile": "mock"}` by default. Profiles, identity, and tool targets are server-owned. To expose selected live profiles, set `ACLAB_PROFILE_DIR` to a directory containing only the intended YAML files; profile names are filename stems. Set `ACLAB_API_KEY` to require `Authorization: Bearer ...`. The CLI requires that key for non-loopback binding. Keep this experimental server local; its API key is not a production identity system.

`ACLAB_MAX_ACTIVE` controls per-worker backpressure; excess active requests receive 429. Connection pools and episode scheduling are bounded. Increasing `--workers` multiplies per-worker limits. The profile name `mock` is reserved so the load command cannot accidentally call a paid model. It does not measure hosted-model throughput.

## Optional One/Blaze and Redis

The default stack uses in-process JSON Schema and actual CEL evaluation. No Docker is needed.

```bash
docker compose --profile one up --build -d one
aclab bench --config configs/one-mock.yaml --matrix single --tasks 12 --repeats 1 --output results/one-smoke
docker compose --profile cache up -d redis
```

Set `cache: redis` in a copied semantic-evaluator profile and `REDIS_URL` in `.env` to use Redis. Use `--matrix cache` to compare it with disabled caching. Only semantic verdicts are cached; state, authorization, approval, and target version are checked again. One is used for schema publication/evaluation; it does not execute the business workflow. The adapter checks remote schema content against the local contract before use and fails closed on drift or unavailability. The Docker integrations require separate verification on your machine; Docker and Redis were unavailable in the build environment.

## Repository guide

- `src/aclab/`: provider adapters, registry, CEL policies, gateway, sandbox, runner, metrics, API, CLI.
- `contracts/`: versioned declarative contracts; `scripts/build_catalog.py` generates packaged schemas and One inputs.
- `configs/`: explicit planner/evaluator/validator/cache profiles.
- `tests/`: malformed input, trust boundaries, semantic failures, retries, races, partial results, caches, adapters, metrics, API backpressure.
- `evidence/`: locally verified mock episodes, evaluator checks, HTTP load results, and verification record.
- `docs/ARCHITECTURE.md`: chart mapping, trust boundaries, scalability and recovery.
- `docs/EXPERIMENTS.md`: evidence protocol and economic decision criteria.
- `docs/RESEARCH.md`: design analysis, corrections, viability, primary sources.
- `docs/EXTENDING.md`: custom tasks, models, and service domains.
- `docs/LIMITATIONS.md`: the boundaries of current claims.

The useful first milestone is a reproducible improvement over a strong baseline on held-out workflows. A universal reliability platform or a claim of lower model latency needs considerably more evidence.
