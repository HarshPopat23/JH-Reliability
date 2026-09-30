# What we are building and whether it is worth it

Research checked against primary documentation on 2026-09-29. Provider interfaces and model availability can change; exact model IDs and rates remain user configuration. No paid inference was performed while building this repository.

## The idea in plain language

An ordinary tool definition tells an agent the operation name and argument shape. An enriched contract also explains when to use it, when not to use it, what state must be true, what it changes, how it fits a workflow, and what to do when execution is uncertain. A runtime then checks whichever parts can be enforced, rather than relying entirely on the agent to remember them.

For example, an issue-closing request might require a linked change to be merged. The model reads the issue and change; CEL checks that the trusted change state actually satisfies the rule. A semantic evaluator can inspect whether the proposed closing reason matches the user's request. Permissions still come from the authenticated service. After execution, the gateway checks the returned structure and intended effect. A timeout triggers an outcome lookup before another write.

The product hypothesis is therefore a contract-authoring and execution layer for reliable tool use, with an evidence harness around it. It is not model training, a universal truth detector, or a replacement for authorization at the target API.

## Honest viability assessment

**Worth building as a focused experiment: yes. Worth treating as a proven general-purpose product today: no.** The valuable problem is reducing wrong but syntactically valid actions and making uncertain execution observable. This repository makes that hypothesis testable. It does not establish market demand or superiority over existing application-specific controls.

My engineering judgment is that the strongest first use case is one domain with costly mutations, clear state rules, and repeatable failures: refunds, account changes, support transitions, or similar workflows. In such a setting, deterministic gates and outcome reconciliation can have value even when a model is already good at producing valid JSON. This is an inference from the architecture, not a measured result.

The weaker pitch is “extra metadata automatically makes every model faster and reliable.” Better descriptions can add tokens, confuse a model, or duplicate native tooling. Semantic judges add inference cost and new failure modes. Contract creation, updates, annotation, and integration are recurring expenses. Customer value must survive comparison with a good prompt, provider tool constraints, target-side business logic, and a modest deterministic gateway.

A credible product moat would come from high-quality domain contracts, real failure datasets, trustworthy state integration, useful diagnostics, and low-maintenance adoption. A new metadata key by itself is easy to reproduce. This is a strategic inference, not a survey of paying customers or a claim that there are no competitors.

## Corrections incorporated

| Initial assumption | Correct interpretation | Repository choice |
|---|---|---|
| JSON Schema proves an operation is appropriate | It checks structure and expressed constraints; valid arguments can have wrong intent | Separate schema, CEL policy, semantic evaluation, and final-state scoring |
| A schema engine executes business workflows | One publishes/evaluates schemas; tool execution is another system | Optional One adapter; explicit sandbox executor |
| CEL and OPA policies are interchangeable | CEL and Rego are distinct languages and engines | Actual CEL expressions through cel-python |
| The model can claim sufficient permission | Authority must come from trusted identity and target policy | Server-owned actor/scopes/tenant; common service ACL checks |
| A semantic confidence score means an action is safe | Confidence needs calibration and can be wrong | allow/block/review, threshold, separate evaluator tests, deterministic vetoes |
| A cached allow can skip the rest of the pipeline | Context and authority can change | Complete dependency keys; fresh state/permission/approval checks |
| A timeout means retry the mutation | The write may already have happened | Deduplication, outcome lookup, state-change detection, stop on uncertainty |
| Output validation undoes a bad mutation | Verification occurs after effects | Reconciliation or review; no claimed rollback |
| A schema microbenchmark proves lower agent latency | Inference, tool I/O, extra turns, and retries dominate many workloads | End-to-end timings plus stages, cost and failure counts |
| Mock success proves better LLM performance | Scripted agents only check implementation behavior | Explicit scripted evidence labels and real-provider profiles |
| A large generated task count proves generality | Repeated templates remain a narrow dataset | Task-cluster statistics and explicit domain/generalization limits |

## Why improvement is plausible, and why it may fail

Better descriptions can clarify close-versus-reopen, reason codes, integer cents, and state prerequisites. Anthropic's tool-design guidance emphasizes contextual clarity and meaningful evaluation. That supports testing description quality, but supplies no effect size for this repository. The `docs` matrix therefore holds enforcement fixed and measures the change rather than assuming one.

Deterministic checks can reject an invalid type or unmet business condition without asking another model. They make behavior easier to audit and can prevent an action even when the planner repeats a mistake. They can also create false refusals when the contract is incomplete, state is stale, or the application's policy differs from the encoded rule. Domain policy tests are as necessary as schema tests.

Semantic evaluation can catch a valid operation that contradicts the request, such as closing an issue when the user asked only to inspect it. That class is beyond ordinary type checking. A judge also faces the same ambiguity and adversarial text that challenge the planner. Comparing Jev and a general LLM judge on independently labeled cases is essential; neither is assumed superior.

Recovery has a different mechanism: it reduces duplicate writes and makes uncertain outcomes explicit. Reliability may improve because execution is controlled rather than because the planner makes fewer errors. A blocked operation is not successful resolution, and review is not free. The score preserves both completion and disallowed mutations.

Latency improvement depends on avoided wasted work. Fast local predicates are cheap relative to inference, but a remote judge or validator introduces network overhead. Larger descriptions increase input size. The useful comparison is total task completion time and cost per safe success, including retries and refusals, not only nanoseconds spent on schema validation.

## Standards and interface choices

OpenAI, Anthropic, Gemini, and Ollama expose different tool-call payloads. Their official interfaces are normalized into the same proposal type. OpenAI Chat Completions is used here for broad compatibility; this is not a Responses API adapter. Vendor constrained-output modes, thought-state continuity, and provider-specific agent loops are not all reproduced. Keep that boundary explicit when benchmarking model capabilities.

Jev's documented SystemOne API accepts state and questions; Choice answers include a label, confidence, and probabilities. The implementation uses one intent-match question with allow/block/review criteria. Its confidence is checked for finite range and consistent class probabilities. No assumption is made that a Jev model is also a general tool-planning model.

Sourcemeta One indexes schemas during image build and serves schema APIs; its optional integration is useful to investigate shared schema infrastructure and the cost of a remote validator. The default local validator minimizes setup and avoids conflating schema governance with model-quality claims. No Blaze speedup is asserted because that deployment was not measured here.

OpenAPI extension fields are suitable for application metadata, but there is no standardized `x-agent-contract` vocabulary in this repo. Arazzo separately defines workflow-description concepts and is a possible future interoperability target. The current workflow metadata is simpler and does not claim Arazzo conformance.

BFCL provides official function-calling evaluations. Tau-bench studies tool-agent-user interaction and repeated-run reliability. They motivate measuring more than valid JSON, but the present sandbox is not either official benchmark. Its empirical all-repeats-safe metric is documented separately to avoid mislabeling an official score.

## Primary sources

- OpenAI, [Function calling](https://developers.openai.com/api/docs/guides/function-calling): tool definitions and call normalization.
- Anthropic, [Tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works): native Messages tools and tool-use blocks.
- Anthropic, [Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents): tool clarity and evaluation rationale.
- Google, [Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling): native declarations, arguments, and provider-specific constraints.
- Ollama, [Tool calling](https://docs.ollama.com/capabilities/tool-calling): local tool interface.
- TypeSafe, [Jev API reference](https://docs.typesafe.ai/api): SystemOne/Choice request and response shape.
- Sourcemeta, [One getting started](https://one.sourcemeta.com/getting-started/), [configuration](https://one.sourcemeta.com/configuration/), and [HTTP API](https://one.sourcemeta.com/api/): build-time indexing and schema evaluation.
- CEL project, [language specification](https://github.com/cel-expr/cel-spec): declarative expression semantics.
- OpenAPI Initiative, [Arazzo specification](https://spec.openapis.org/arazzo/latest.html): workflow specification boundary.
- Berkeley/Gorilla, [BFCL paper](https://proceedings.mlr.press/v267/patil25a.html) and [official runner](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard): function-call evaluation.
- Yao et al., [tau-bench paper](https://arxiv.org/abs/2406.12045) and [official repository](https://github.com/sierra-research/tau-bench): domain-policy interaction and repeated-run evaluation.

These links support design and protocol choices. They do not establish measured performance for Agent Contract Lab, and no published benchmark effect size is transferred to this project.
