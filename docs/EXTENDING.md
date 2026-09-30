# Extend the experiment

## New task cases

```bash
aclab export-tasks --tasks 72 --seed 42 --output my-tasks.jsonl
aclab bench --config configs/ollama.yaml --matrix single --dataset my-tasks.jsonl --repeats 5 --output results/my-tasks
```

Each line contains a `Task` record from `src/aclab/sandbox.py`: unique ID, category, prompt, issue/change/order starting state, expected goal, fault, mock mistake, and trusted actor fixture. Edit prompt/state/goal together and inspect the scorer. Labels are benchmark-author data, not instructions added to model prompts. Do not merely paraphrase the bundled examples and call them independent workflows.

Task JSONL loading supports the existing sandbox domain; it does not automatically implement new APIs. For a new domain, supply a service implementation with trusted evidence, authorization, exact-action approval where needed, atomic mutation/version enforcement, outcome lookup, mutation history, and independently reviewed scoring. Then update `Runner` to construct that service and replace the task type/loader. Keep score labels outside planner/evaluator inputs.

## New tool contracts

`scripts/build_catalog.py` is the source generator for the packaged catalog, human-readable contracts, and One schemas. Add the contract there, implement the matching service method, add examples and domain policy tests, then regenerate:

```bash
python scripts/build_catalog.py
pytest -q
```

New CEL expressions need explicit trusted activation fields and failure behavior. Contracts are data; they do not dynamically install executable plugins. Each operation must be bound to reviewed executor code. Update the contract version when changing behavior; manifests additionally record the full catalog hash.

Current bundled schemas are self-contained. General remote `$ref` resolution, alternate schema dialects, large array schemas, and provider schema translation require additional work and conformance tests. Gemini uses a schema subset; do not silently discard constraints and assume the provider enforces the full contract. Runtime local/One validation still owns contract validation.

## New model/server

First try `openai_compatible` with the exact endpoint/model and `mode: tools`. Servers vary: unsupported `tools`, `max_tokens`, or temperature should produce visible integration failures rather than be mistaken for weak model reasoning. Use `mode: json` when native tool calling is unsupported, and record that mode as an experimental factor.

For a genuinely different protocol, add a branch to `ModelProvider.propose` returning `Proposal(calls, text, usage)`. Record returned model identity, tokens when available, and HTTP attempts. Preserve secret redaction. Add response fixtures for malformed/missing fields, HTTP errors, and multiple proposed operations. Real tool-result continuation should be a separately versioned adapter mode if added.

The provider `extra_body` option is for reviewed server-specific inference settings. It cannot override model, messages, tools, system prompts, contents, or streaming. Keys and payload secrets belong in environment variables, never committed configuration.

## New semantic examples

`datasets/semantic-dev.jsonl` lines have unique `id`, `request`, `call`, optional `evidence`, and one `label` from allow/block/review. An independent author should include near-miss targets, exact amounts, conditional actions, missing evidence, multilingual/paraphrased requests, prompt injection, and legitimate unusual requests. The evaluator receives only request/call/evidence. Test labels never enter its state.

Use one development file to choose a threshold and a separate test file via `aclab evaluate --dataset ...`. The supplied threshold sweep does not automatically change the runtime threshold. Frozen thresholds avoid tuning on test outcomes.

## Deploying beyond this lab

Prioritize target-side transactional safeguards and durable deduplication before adding more model judges. Add real identity/approval management, quota controls, persistent jobs/results, cross-worker observability, and integration-failure drills. Measure the additional maintenance and incident cost. A larger queue or more workers alone does not make the workflow reliable.
