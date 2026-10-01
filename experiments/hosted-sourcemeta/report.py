import json, statistics
from pathlib import Path
out=Path('results/real-hosted');out.mkdir(parents=True,exist_ok=True)
p=out/'manifest.json'
m=json.loads(p.read_text()) if p.exists() else {'status':'setup_failed','stages':{}}
lines=['# Real Sourcemeta and Qwen hosted pilot report','',f"Execution status: **{m['status']}**.",'','This report includes only results present in the raw evidence. Absent measurements are not zero latency or zero cost. All Qwen inference uses Ollama CPU execution; target tool services are isolated authored sandbox fixtures.','', '| Component | Status | Evidence |','|---|---|---|']
for key in ('native_blaze','one','alterschema','json_binpack','qwen'):
 s=m.get('stages',{}).get(key,{});e=s.get('error',f"{s.get('parity_cases',s.get('schemas',s.get('cases',s.get('completed',''))))} measured cases/schemas/episodes")
 lines.append(f"| {key} | {s.get('status','not measured')} | {str(e).replace('|','/')} |")
p=out/'validator-rounds.json'
if p.exists():
 rs=json.loads(p.read_text());lines+=['','## Native validator audit','',f"{len(rs)} case-round observations with consumed result checksums; 2,000 validations per batch. Timing excludes JSON parse and transport. The Python and native checks both return boolean validity. These are diverse synthetic contract cases, not complete specification conformance tests.",'','| Engine | Mean ns/check | Median ns/check |','|---|---:|---:|']
 for key,label in [('python_ns_per_op','Python jsonschema'),('blaze_ns_per_op','Native Blaze'),('transformed_ns_per_op','AlterSchema + native Blaze')]:
  xs=[r[key] for r in rs];lines.append(f'| {label} | {statistics.mean(xs):.1f} | {statistics.median(xs):.1f} |')
 lines+=['','IPC batch timing includes serialization, parse, the full batch, and transport. It is not a single-call gateway latency. See episodes for actual per-call IPC/gateway timings. Python cold validator construction and native schema compilation perform different setup work. No end-to-end speedup can be inferred from kernel speed alone.']
p=out/'qwen-summary.json'
if p.exists():
 rs=json.loads(p.read_text());lines+=['','## Matched Qwen comparison','', '| Arm | Episodes | Safe success | Unsafe writes | Errors | Wall p50 ms | Wall p95 ms | Planner calls | Input tokens* | Output tokens* |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
 for r in rs:
  l=r['latency_ms'];lines.append(f"| {r['arm']} | {r['episodes']} | {r['safe_success']}/{r['episodes']} | {r['unsafe_actions']} | {r['errors']} | {l['p50']:.1f} | {l['p95']:.1f} | {r['model_calls']} | {r['input_tokens']} | {r['output_tokens']} |")
 lines+=['','*Tokens include semantic judge calls where the gateway recorded usage. Planner calls exclude judge calls; raw Ollama telemetry gives the actual request total. The full arm uses Qwen as judge, not Jev. Missing token usage stays unknown.','', '12 matched tasks and 1 repeat per arm constitute a pilot. No reliable production generalization, scalability, or stochastic confidence claim follows from this sample. Pair episode outcomes by task ID before attributing differences to validators.']
else:lines+=['','## Qwen comparison','', 'The complete matched Qwen table is not available. Partial episodes, if present, remain partial evidence; do not compare unequal task coverage.']
p=out/'binpack.json'
if p.exists():
 rs=json.loads(p.read_text());lines+=['','## JSON BinPack storage study','', '| Contract | JSON bytes | BinPack bytes | Round trips correct | Mean encode ns | Mean decode ns |','|---|---:|---:|---:|---:|---:|']
 for r in rs:
  if 'error' in r:lines.append(f"| {r['key']} | unavailable | unavailable | ERROR | unavailable | unavailable |")
  else:lines.append(f"| {r['key']} | {r['json_utf8_bytes']} | {r['bytes']} | {r['correct']}/{r['rounds']} | {r['encode_ns_total']/r['rounds']:.1f} | {r['decode_ns_total']/r['rounds']:.1f} |")
 lines+=['','Size comparisons exclude the schema/encoding distribution cost. Ollama consumes JSON, so binary storage is tested separately and does not reduce model input tokens. Small instances may not represent production payloads.']
lines+=['','## Interpretation limits','', 'One registry governance and HTTP evaluation are different operations. HTTP trace/evaluation may perform exhaustive diagnostics and annotations, so it is not equivalent work to native boolean validation. Registry checks test a pinned schema mismatch and a real paused-container outage; they do not establish authorization, update propagation, or high-availability guarantees.','', 'AlterSchema applies genuine schema Linter transformations. It is not an arbitrary state canonicalizer, and deterministic JSON hashing does not establish universal semantic schema equivalence.','', 'The baseline preserves primitive target security. Optional policy checks can prevent unsafe retries but cannot undo already committed partial effects. Full-arm reliability depends on an imperfect real Qwen judge.','', 'Paid API spend: none. Hardware rental accounting, electricity, dollar cost per successful task, and production concurrency were not measured. A CPU pilot cannot establish laptop or GPU latency.','', 'Raw evidence: manifest.json, validator-rounds.json, one-verification.json, alterschema.json, binpack.json, episodes.jsonl, qwen-telemetry.jsonl, model/settings/source identity and setup logs.']
(out/'REPORT.md').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))
