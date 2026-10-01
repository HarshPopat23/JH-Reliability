"""Detailed evidence-only layer/context report, generated after all artifacts exist."""
import argparse
import importlib.util
import json
import statistics
import random
from jsonschema import Draft202012Validator
from pathlib import Path

spec=importlib.util.spec_from_file_location('study',Path(__file__).with_name('study.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def median(values):return statistics.median(values) if values else None

GOLD={t['id']:t for t in m.tasks()}
BODY_VALIDATOR=Draft202012Validator(m.BODY)

def semantic_candidate(row):
 """Goal semantics plus body contract, allowing any nonempty idempotency key."""
 proposal=row.get('proposal')
 if not isinstance(proposal,dict):return False
 body=proposal.get('body')
 if not BODY_VALIDATOR.is_valid(body):return False
 gold=GOLD[row['task_id']]['gold']
 return all(body[k]==gold[k] for k in ['resource','value','unit','expected_version'])

def verified_completion(row,without=False):
 if not semantic_candidate(row):return False
 branch=row.get('without_blaze') or {} if without else row
 status=branch.get('http_status') if without else row.get('api_status')
 response=branch.get('response') if without else row.get('api_response')
 if status!=200 or not isinstance(response,dict):return False
 if response.get('status') not in ['done','duplicate'] or response.get('version')!=GOLD[row['task_id']]['version']+1:return False
 if without:return branch.get('backend_writes')==1
 return any(c['direction']=='output' and c['valid'] for c in row['native_calls'])

def cluster_rate(rows,key):
 groups={}
 for row in rows:groups.setdefault(row['task_id'],[]).append(float(row[key]))
 values=[statistics.mean(groups[key]) for key in sorted(groups)]
 if not values:return None
 rng=random.Random(913);draws=sorted(statistics.mean(rng.choices(values,k=len(values))) for _ in range(2000))
 return {'rate':statistics.mean(values),'ci95':[draws[49],draws[1949]],'task_clusters':len(values)}

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',default='service-corrected-evidence');p.add_argument('--output',default='results/service-understanding-final');p.add_argument('--native-replay');p.add_argument('--one-replay');a=p.parse_args()
 native_replay=json.loads(Path(a.native_replay).read_text()) if a.native_replay else None
 one_replay=json.loads(Path(a.one_replay).read_text()) if a.one_replay else None
 root=Path(a.input);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 grouped={};infrastructure=[];registry=[];identities=[];manifests=[]
 for f in sorted(root.rglob('episodes.jsonl')):
  manifest=json.loads(f.with_name('manifest.json').read_text());manifests.append(manifest)
  grouped.setdefault(manifest['model'],[]).extend(json.loads(line) for line in f.read_text().splitlines() if line.strip())
  infrastructure.append(json.loads(f.with_name('infrastructure.json').read_text()))
  identities.append(json.loads(f.with_name('model-identities.json').read_text()))
  rp=f.with_name('registry-probes.json')
  if rp.exists():registry.append(json.loads(rp.read_text()))
 for rows in grouped.values():
  for row in rows:
   row['semantic_candidate']=semantic_candidate(row)
   row['verified_completion']=verified_completion(row)
   row['verified_without_completion']=verified_completion(row,True)
 if set(grouped)!={'qwen3:4b-instruct','gemma3:1b'}:raise RuntimeError('Both complete model corpora are required')
 data={};lines=['# JH-Reliability: schema context and native gateway experiment','','## What ran','',
  'Real Qwen3 4B Instruct and Gemma3 1B through pinned Ollama, native Sourcemeta Blaze/AlterSchema, and live Sourcemeta One containers on GitHub-hosted Linux CPUs. Synthetic services for refunds, scheduling and public-only exports. 24 tasks, five repeats, seven documentation variants; twelve tasks for development and twelve held out.',
  '', 'A generic output envelope is constrained during decoding. Service-specific unit enums and version requirements are supplied as context and enforced independently by Blaze. Executed candidates are sent to fresh sandbox states with and without Blaze, with identical backend rules. Abstentions are not executed. No model reconsideration or retry loop is tested.',
  '', 'Scoring disclosure: the frozen primary endpoint requires the exact task-specific idempotency key. During inspection of the first two completed Gemma shards, some actions completed correctly using a different nonempty key. Raw scores and logs are preserved. Backend-verified completion and semantic correctness are disclosed post-hoc secondary endpoints, applied identically to every model and arm; they must not be presented as pre-registered results. Alternate keys are assessed only in fresh per-task sandboxes. Copied example keys remain instruction-fidelity errors and could cause collisions in a shared production journal; this scoring does not establish safe idempotency across operations.',
  '', '| Model | Documentation | Held-out n | Strict request match | Semantically correct body | Verified completion with Blaze | Failed API calls without Blaze | Blaze input/output rejects | Failed API calls with Blaze | Model errors |',
  '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
 for model,rows in sorted(grouped.items()):
  rows.sort(key=lambda r:(r['task_id'],r['arm'],r['repeat']))
  keys=[(r['task_id'],r['arm'],r['repeat']) for r in rows]
  if len(set(keys))!=len(keys):raise RuntimeError('Duplicate episode keys')
  expected={(t['id'],arm,r) for t in m.tasks() for arm in m.ARMS for r in range(5)}
  if set(keys)!=expected:raise RuntimeError(f'Incomplete coverage for {model}: {len(keys)}/{len(expected)}')
  held=[r for r in rows if r['split']=='test'];summaries=[]
  for arm in m.ARMS:
   rs=[r for r in held if r['arm']==arm]
   item={'arm':arm,'n':len(rs),'correct':sum(r['correct_candidate'] for r in rs),'safe_success':sum(r['safe_success'] for r in rs),
    'semantic_correct':sum(r['semantic_candidate'] for r in rs),'verified_completion':sum(r['verified_completion'] for r in rs),
    'key_only_mismatch':sum(r['semantic_candidate'] and not r['correct_candidate'] for r in rs),
    'without_failed_api':sum((r.get('without_blaze') or {}).get('http_status',0)>=400 for r in rs),
    'with_failed_api':sum(r['backend_rejected'] for r in rs),'schema_rejected':sum(r['schema_rejected'] for r in rs),
    'errors':sum(bool(r['error']) for r in rs),
    'model_duration_ms_median':median([r['raw_response']['total_duration']/1e6 for r in rs if r.get('raw_response',{}).get('total_duration')]),
    'input_tokens':sum(r.get('raw_response',{}).get('prompt_eval_count') or r['input_tokens'] or 0 for r in rs),
    'output_tokens':sum(r.get('raw_response',{}).get('eval_count') or r['output_tokens'] or 0 for r in rs),
    'completion_ci':cluster_rate(rs,'verified_completion'),'semantic_ci':cluster_rate(rs,'semantic_candidate'),
    'strict_ci':cluster_rate(rs,'correct_candidate'),
    'families':{family:{'n':sum(r['family']==family for r in rs),
      'semantic_correct':sum(r['family']==family and r['semantic_candidate'] for r in rs),
      'completion':sum(r['family']==family and r['verified_completion'] for r in rs)} for family in m.FAMILIES},
    'abstentions':sum(isinstance(r.get('proposal'),dict) and r['proposal'].get('action')=='abstain' for r in rs),
    'valid_but_semantically_wrong':sum(not r['semantic_candidate'] and any(c['direction']=='input' and c['valid'] for c in r['native_calls']) for r in rs),
    'confident_semantically_wrong':sum((r['probability'] or 0)>=.9 and not r['semantic_candidate'] for r in rs),
    'without_completion':sum(r['verified_without_completion'] for r in rs),
    'strict_pass5_tasks':sum(len(ts)==5 and all(x['safe_success'] for x in ts) for ts in
      [[x for x in rs if x['task_id']==tid] for tid in sorted({x['task_id'] for x in rs})]),
    'pass5_tasks':sum(len(ts)==5 and all(x['verified_completion'] for x in ts) for ts in
      [[x for x in rs if x['task_id']==tid] for tid in sorted({x['task_id'] for x in rs})]),
    'test_tasks':len({x['task_id'] for x in rs})}
   summaries.append(item)
   lines.append(f"| {model} | {arm} | {item['n']} | {item['correct']}/{item['n']} | {item['semantic_correct']}/{item['n']} | {item['verified_completion']}/{item['n']} | {item['without_failed_api']} | {item['schema_rejected']} | {item['with_failed_api']} | {item['errors']} |")
  contrast={f'{x}-{y}':m.bootstrap(rows,x,y,'correct_candidate') for x,y in [('rich','poor'),('rich','moderate'),('rich','prose'),('false','rich'),('stale','rich')]}
  secondary_contrast={f'{x}-{y}':m.bootstrap(rows,x,y,'verified_completion') for x,y in [('rich','poor'),('rich','moderate'),('rich','prose'),('false','rich'),('stale','rich')]}
  calibration=m.calibration(rows)
  semantic_calibration=m.calibration([{**r,'correct_candidate':r['semantic_candidate']} for r in rows])
  calls=[c for r in rows for c in r['native_calls']]
  parity={'checked_input_proposals':0,'true_reject':0,'false_reject':0,'true_accept':0,'false_accept':0}
  validators={f:Draft202012Validator(m.contract(f)) for f in m.FAMILIES}
  for row in rows:
   input_call=next((c for c in row['native_calls'] if c['direction']=='input'),None)
   if input_call is None:continue
   valid=validators[row['family']].is_valid(row['proposal']['body']);parity['checked_input_proposals']+=1
   parity[('true_accept' if valid else 'false_accept') if input_call['valid'] else ('false_reject' if valid else 'true_reject')]+=1
  data[model]={'retained_episodes':len(rows),'heldout':summaries,'contrasts':contrast,'secondary_completion_contrasts':secondary_contrast,'calibration':calibration,'semantic_calibration':semantic_calibration,'offline_validator_parity':parity,
   'actual_native_calls':len(calls),'native_engine_ns_median':median([c['engine_ns'] for c in calls]),
   'native_ipc_ns_median':median([c['ipc_wall_ns'] for c in calls]),
   'layer_completion_difference':sum(int(r['verified_completion'])-int(r['verified_without_completion']) for r in held),
   'confident_semantically_wrong':sum((r['probability'] or 0)>=.9 and not r['semantic_candidate'] for r in held),
   'length_limited_errors':sum(bool(r['error']) and r.get('raw_response',{}).get('done_reason')=='length' for r in rows),
   'incomplete_response_errors':sum(bool(r['error']) and r.get('raw_response',{}).get('done') is False for r in rows),
   'missing_token_counter_episodes':sum('eval_count' not in r.get('raw_response',{}) or 'prompt_eval_count' not in r.get('raw_response',{}) for r in rows),
   'error_types':{e:sum(r['error']==e for r in rows) for e in sorted({r['error'] for r in rows if r['error']})}}
 lines+=['','## Paired context effects: frozen strict matching','','Differences in percentage points, with 95% bootstrap intervals over matched held-out task clusters. Each model has twelve held-out task clusters; repeated episodes do not count as independent tasks. These are exploratory contrasts; no broad population-level significance or multiplicity-adjusted claim is made.','',
  '| Model | Contrast | Difference | 95% interval |','|---|---|---:|---|']
 for model,d in data.items():
  for label,c in d['contrasts'].items():
   if c:lines.append(f"| {model} | {label} | {100*c['difference']:.1f} pp | [{100*c['ci95'][0]:.1f}, {100*c['ci95'][1]:.1f}] pp |")
 lines+=['','## Secondary paired effects: backend-verified completion','','Post-hoc completion scoring removes exact idempotency-key matching; it still requires a contract-valid body, correct goal values, HTTP 200, expected response state, and successful native output validation.','',
  '| Model | Contrast | Difference | 95% interval |','|---|---|---:|---|']
 for model,d in data.items():
  for label,c in d['secondary_completion_contrasts'].items():
   if c:lines.append(f"| {model} | {label} | {100*c['difference']:.1f} pp | [{100*c['ci95'][0]:.1f}, {100*c['ci95'][1]:.1f}] pp |")
 lines+=['','## Decision understanding, abstention and semantic failures','','Body accuracy scores the proposed request even when action is abstain. Actual completion requires execution. A contract-valid request can still have the wrong amount, timestamp or resource. High confidence is not independently verified confidence.','',
  '| Model | Documentation | Semantic accuracy, 95% task-cluster interval | Abstentions | Valid but semantically wrong executions | Non-correct bodies with probability >=0.9 | Exact-key-only mismatches |',
  '|---|---|---|---:|---:|---:|---:|']
 for model,d in data.items():
  for s in d['heldout']:
   c=s['semantic_ci'];lines.append(f"| {model} | {s['arm']} | {100*c['rate']:.1f}% [{100*c['ci95'][0]:.1f}, {100*c['ci95'][1]:.1f}] | {s['abstentions']} | {s['valid_but_semantically_wrong']} | {s['confident_semantically_wrong']} | {s['key_only_mismatch']} |")
 lines+=['','Intervals that collapse to 0% or 100% reflect a small authored sample with no observed within-sample variation; they do not imply certainty for unseen workflows. The same caution applies to bootstrap differences.','',
  '## Output budget failures','', '| Model | Errors | Errors ending at output limit | Incomplete done=false errors | Episodes missing token counters |','|---|---:|---:|---:|---:|']
 for model,d in data.items():lines.append(f"| {model} | {sum(d['error_types'].values())} | {d['length_limited_errors']} | {d['incomplete_response_errors']} | {d['missing_token_counter_episodes']} |")
 lines+=['','All arms use the same 128-token output budget. Budget truncation remains a failure in every task denominator. Token totals include truncated responses where counters exist, even where parsing failed; an incomplete Gemma response lacked counters, so token totals are reported counts rather than a fully known session total. This budget limits interpretation: malformed outputs at the cap do not alone establish intrinsic JSON-generation failure.']
 lines+=['','## Service-family breakdown','','Each cell is semantically correct bodies / verified completed actions / 20 held-out episodes. Gemma successes are limited to export tasks; neither money nor timestamp conversions succeeded. This prevents pooled rates from hiding that weakness.','',
  '| Model | Documentation | Refund | Schedule | Export |','|---|---|---|---|---|']
 for model,d in data.items():
  for s in d['heldout']:
   cells=[f"{s['families'][f]['semantic_correct']} / {s['families'][f]['completion']} / {s['families'][f]['n']}" for f in m.FAMILIES]
   lines.append(f"| {model} | {s['arm']} | "+' | '.join(cells)+' |')
 lines+=['','## Latency and token use','','Model duration comes from the actual Ollama response and excludes the duplicate gateway execution used by this experiment. Reported episode wall time in raw records includes both layer branches and is not production end-to-end latency. Hosts differ in CPU hardware, so cross-model timing is descriptive rather than a controlled hardware speed comparison.','',
  '| Model | Documentation | Median model duration ms | Input tokens | Output tokens |','|---|---|---:|---:|---:|']
 for model,d in data.items():
  for s in d['heldout']:lines.append(f"| {model} | {s['arm']} | {s['model_duration_ms_median']} | {s['input_tokens']} | {s['output_tokens']} |")
 lines+=['','## Repeat stability','','pass^5 means all five repeated episodes completed safely for a task; it is not pass@5 (any successful attempt).','',
  '| Model | Documentation | Strict success all five repeats | Verified completion all five repeats |','|---|---|---:|---:|']
 for model,d in data.items():
  for s in d['heldout']:lines.append(f"| {model} | {s['arm']} | {s['strict_pass5_tasks']}/{s['test_tasks']} | {s['pass5_tasks']}/{s['test_tasks']} |")
 lines+=['','## What Blaze changed','','| Model | Actual native calls, all episodes | Median native engine ns | Median IPC wall ns | Held-out completion difference, with minus without |','|---|---:|---:|---:|---:|']
 for model,d in data.items():lines.append(f"| {model} | {d['actual_native_calls']} | {d['native_engine_ns_median']} | {d['native_ipc_ns_median']} | {d['layer_completion_difference']} |")
 lines+=['','Blaze acceptance/rejection is independently cross-checked against Python Draft 2020-12 validation offline, after inference timing. This checks structural contract validity, not semantic safety.','',
  '| Model | Input proposals checked | Correct rejects | False rejects | Correct accepts | False accepts |','|---|---:|---:|---:|---:|---:|']
 for model,d in data.items():
  v=d['offline_validator_parity'];lines.append(f"| {model} | {v['checked_input_proposals']} | {v['true_reject']} | {v['false_reject']} | {v['true_accept']} | {v['false_accept']} |")
 lines+=['','Blaze does not change the model proposal in this design. A reduction in failed HTTP calls means contract violations were stopped before reaching the service, not that the task was repaired. The backend is deliberately strict and rejects semantic mismatches against executable reference state; therefore zero unsafe writes are strongly determined by backend safeguards, not evidence that schemas guarantee safety.',
  '', '## Calibration','','| Model | Label target | Probability variant | Held-out probability observations | Brier | ECE |','|---|---|---|---:|---:|---:|']
 for model,d in data.items():
  for target,key in [('strict exact request','calibration'),('semantic body (secondary)','semantic_calibration')]:
   for variant in ['raw','dev_fit_histogram']:
    c=d[key][variant]
    if c:lines.append(f"| {model} | {target} | {variant} | {c['n']} | {c['brier']:.4f} | {c['ece']:.4f} |")
 lines+=['','Raw probabilities are self-reported estimates of proposal correctness. The postprocessor is fitted only on development labels and does not alter model choices. Probability metrics exclude episodes without valid probability output; task-completion denominators still include errors. A global calibration mapping can hide subgroup differences. This pilot does not establish either model as calibrated, and schema validity cannot establish confidence reliability.',
  '', 'Gemma puts all usable held-out probabilities in the top raw bin. Histogram calibration therefore mostly replaces its confidence with a pooled development success rate. Lower ECE from this nearly constant score is not improved decision discrimination; at thresholds above that base rate it rejects every candidate. Threshold observations are retained in detailed-analysis.json.',
  '', '## One, AlterSchema and backend checks','',f'Live registry probe artifacts: {len(registry)}. Passed: {sum(x["status"]=="passed" for x in registry)}.',
  '', 'One fetches were digest-checked against frozen authoritative input contracts. The model documentation was generated locally; One did not supply the rich OpenAPI descriptions in this study. Four concurrent clients fetched v1, then explicitly switched to v2; outage fetches failed closed and recovery was checked. These tests establish versioned serving and explicit client selection, not automatic discovery of an approval change, auth permissions, or a causal One-on/off model accuracy gain. Versioned contracts were deployed together, without server hot reload.',
 '', 'AlterSchema performed genuine native linter transformations as a separate infrastructure probe. Those transformed schemas were not substituted into model context or the timed gateway validator. Compiled-validator reuse was independently compared with fresh worker startup/compilation: the cold measurement includes process startup and IPC, while the warm measurement includes IPC, parsing and validation. This measures worker reuse, not an AlterSchema-caused speedup, semantic deduplication, model-decision caching, or a reduction in inference calls.',
  '', 'Ownership, consent, state-race and concurrent idempotency probes run independently of model episodes. These fixture checks use a simulated backend; they do not establish resilience of production databases or distributed transactions.',
  '', '## Limits and exact attribution','',
  '- Rich versus poor changes both available facts and documentation length. Some service facts are genuinely unavailable without documentation; this tests usefulness of supplied contracts rather than stronger general reasoning.',
  '- Rich versus matched prose tests presentation with similar facts, but not a standalone JSON Schema versus OpenAPI comparison. Rich uses OpenAPI with JSON Schema bodies; their separate contributions are not identified.',
  '- False documentation deliberately contradicts correct assertions about units; stale documentation describes a prior version. These are robustness conditions, not information-matched richness comparisons.',
  '- Only three authored service families and twelve held-out tasks; no human-reviewed semantic labels, real production services, equal-token control, multi-turn correction loop, or deployment-level calibration claim.',
  '- All model arms share one output envelope. Native unit/version contract checks are stricter than that envelope, allowing actual runtime validation failures.',
  '- In these toy contracts expected_version is a fixed constant aligned with the deployed contract version. This is an authored snapshot constraint, not proof that JSON Schema can query live resource state. A production API should distinguish interface version from resource concurrency version and enforce the latter against backend state.',
  '- Dollar cost and energy savings were not measured. Every retained episode makes one model call; the matched layer comparison adds no model retry. Avoided backend requests are not evidence of reduced model-token costs.',
  '- JSON BinPack is not part of this study. AlterSchema equivalence/canonical hash behavior is not established by the separate transformation probe, and cache savings cannot be attributed to AlterSchema.',
  '- The initial run 36905170453 completed zero episodes after native startup failed. It is excluded from all model comparisons. The corrected source commit is 8e79ddec72a63f8bf07c0e2f77d306771e87f8b1; raw manifests and model digests pin the retained evidence.',
  '', 'Raw evidence: GitHub Actions run https://github.com/HarshPopat23/JH-Reliability/actions/runs/36907463064 . Read audit.json and detailed-analysis.json before drawing conclusions.']
 lines+=['','## Infrastructure timings and scope','','Each row is one independently provisioned job. These are direct component measurements, not full-task speedups.','',
  '| Shard/model | One verified fetches | Four-agent refresh/outage/recovery | Warm cached worker median µs | Fresh worker startup + compile + validation median µs | Native AlterSchema CLI median µs |',
  '|---|---:|---|---:|---:|---:|']
 for manifest,infra in zip(manifests,infrastructure):
  c=infra['compiled_cache']
  lines.append(f"| {manifest['model']} shard {manifest.get('shard')} | {len(infra['one'])} | See corresponding registry-probes.json | {median(c['warm_ipc_wall_ns'])/1000:.2f} | {median(c['fresh_process_compile_ipc_wall_ns'])/1000:.2f} | {median([r['wall_ns'] for r in infra['alterschema']])/1000:.2f} |")
 lines+=['','Native output-contract negative controls also rejected the malformed response {"acknowledged": true} for all three service families before timed episodes; the worker source contains those asserted live checks. The backend probe named unexpected_response_python_control is a separate Python-only control and is not a native measurement. Runtime native-call counts above exclude setup controls and cache microbenchmarks.']
 if native_replay and one_replay:
  lines+=['','## Post-hoc native and live One replay','','Qwen abstentions never reach the timed gateway. To test conformance of its real generated bodies, every saved body was evaluated again in a separately built native Blaze worker and over real HTTP in an actual One container. No new inference, task execution or retry occurred. This is post-hoc contract evidence, not a repaired task-completion score.','',
   '| Model | Saved bodies | Native rejects | One HTTP rejects | Offline reference disagreements | Native engine median µs | Native IPC median µs | One HTTP p50 / p95 / p99 ms, concurrency 8 |',
   '|---|---:|---:|---:|---:|---:|---:|---|']
  for model,n in native_replay['models'].items():
   o=one_replay['models'][model]
   lines.append(f"| {model} | {n['bodies']} | {n['rejected']} | {o['rejected']} | {n['parity_mismatches']+o['parity_mismatches']} | {n['engine_ns_median']/1000:.3f} | {n['ipc_wall_ns_median']/1000:.3f} | {o['http_ns_p50']/1e6:.3f} / {o['http_ns_p95']/1e6:.3f} / {o['http_ns_p99']/1e6:.3f} |")
  lines+=['','One also returned actual detailed traces for three valid and three invalid-unit fixtures, and three dependency responses. HTTP timings include client serialization, transport and service processing under eight concurrent clients; native IPC uses a serialized worker on another host. They are not a matched native-engine versus HTTP speed comparison.',
   '', 'Native replay: https://github.com/HarshPopat23/JH-Reliability/actions/runs/36913205724 . Live One replay: https://github.com/HarshPopat23/JH-Reliability/actions/runs/36914860098 . Their immutable source commits differ from the original model run; see provenance below and raw artifact manifests.']
 definitions=['','## Documentation variants','', '| Variant | Information supplied |','|---|---|',
  '| none | Generic envelope and task; no service-specific unit documentation |',
  '| poor | Basic body fields and types |',
  '| moderate | Authoritative unit enum, version and other assertions, without explanatory semantics |',
  '| rich | OpenAPI 3.1 wrapper, JSON Schema assertions, correct descriptions and examples |',
  '| prose | Similar correct interface facts described in prose; approximate information control |',
  '| false | Deliberately wrong semantic descriptions, while current structural assertions remain correct |',
  '| stale | Coherent previous-version contract and units, conflicting with current task version |',
  '', 'The three authoritative input schemas require resource (string), value (nonnegative integer), unit (family-specific enum), expected_version (const 2), and a nonempty idempotency_key, with additionalProperties false. Refunds use minor currency units; scheduling uses Unix milliseconds; exports use public_only. The shared output schema requires status in done/duplicate and a positive integer version. These simple schemas and backend states are frozen in study.py.', '']
 lines[2:2]=definitions
 q={s['arm']:s for s in data['qwen3:4b-instruct']['heldout']}
 g={s['arm']:s for s in data['gemma3:1b']['heldout']}
 without=sum(s['without_failed_api'] for s in g.values());with_layer=sum(s['with_failed_api'] for s in g.values())
 findings=['','## Main findings','',
  f"This run retained {sum(d['retained_episodes'] for d in data.values()):,} real model episodes. Each documentation condition has 60 held-out episodes per model (12 tasks × five repeats).",
  '', f"Qwen produced semantically correct bodies in {q['rich']['semantic_correct']}/60 rich cases and {q['prose']['semantic_correct']}/60 prose cases, versus {q['poor']['semantic_correct']}/60 basic-schema cases. It mostly abstained: rich completed {q['rich']['verified_completion']}/60 actions; prose completed {q['prose']['verified_completion']}/60. This supports a benefit from supplied service facts, but does not establish a unique declarative-syntax advantage or reliable task execution.",
  '', f"Gemma completed {g['moderate']['verified_completion']}/60 moderate-schema cases, {g['rich']['verified_completion']}/60 rich cases, and {g['prose']['verified_completion']}/60 prose cases. All its successes were export tasks; it failed both conversion families. Richer documentation was not uniformly better for this small model.",
  '', f"Across the seven held-out Gemma conditions, native Blaze reduced failed HTTP service calls from {without} to {with_layer} ({100*(without-with_layer)/without:.1f}% fewer), while completed actions were unchanged. This is request filtering, not model correction, a production traffic forecast, or a model-token cost saving.",
  '', 'Live One registry/version/outage checks and the separate HTTP conformance replay worked. They do not isolate a One-caused model accuracy improvement. Native AlterSchema ran only as a separate probe; it cannot be credited with a model-quality or cache-speed improvement here.',
  '', 'Rich context increased prompt tokens and median inference duration. No end-to-end latency, dollar-cost, energy, or universally safer full-stack improvement is established. Completion scoring was corrected post hoc as disclosed below; raw exact-match scores remain available for audit.',
  '', 'Read the limits before sharing these results. They concern three synthetic service families, not general model intelligence or production reliability.', '']
 lines[2:2]=findings
 lines+=['','## What remains to establish','',
  '1. Diagnose Qwen action abstention with explicit action instructions and counterbalanced enum/prompt controls. Keep proposed-body accuracy separate from execution.',
  '2. Pre-register separate semantic completion and idempotency-instruction metrics, require complete Ollama responses, and rerun all matched conditions with a sufficient common output budget.',
  '3. Add independently reviewed real or realistic services, unseen service families, more held-out tasks, and equal-fact/equal-token controls separating JSON Schema, OpenAPI and prose.',
  '4. Retrieve actual model-facing descriptions from One, change an approved version while agents run, and test application refresh/TTL behavior against pinned and stale clients.',
  '5. Compare no retry, generic validation feedback and detailed trace feedback with matched maximum model attempts and unchanged backend safeguards.',
  '6. Test worker pools and 50+ concurrent requests; the current native bridge serializes calls, while One HTTP replay used eight concurrent clients.',
  '7. Preserve transformed schemas and test validation equivalence over diverse instances before attributing cache benefits to AlterSchema. Validator-cache keys may ignore non-validating annotations only when safe for that consumer; model-context caches must include descriptions/examples, versions, model settings and relevant state.',
  '8. Measure inference/backend/registry costs and energy explicitly. A constant calibrated base-rate estimate is not a useful semantic judge or a guarantee against confident wrong decisions.',
  '', '## Provenance','',
  '- Model experiment: 8e79ddec72a63f8bf07c0e2f77d306771e87f8b1, run 36907463064.',
  '- Native replay: cdabfb18eabdb79cdf0fa53d4badb1ceabb7d89f, run 36913205724.',
  '- One HTTP replay: e1f73c0e40ffb9094bc7218ad2025bf013deed53, run 36914860098.',
  '- Blaze source: 059dbed08ea26bd9a630bad5eb07421f4cc34cc0. Ollama: 0.32.0. Both models: Q4_K_M.',
  '- Observed official One 6.7 image digest: sha256:0a68085e2842b461d06518c145a209132b4fbcdb9ef76088645466787f22ba8f. The follow-up Dockerfile pins this digest for reproduction; the executed model source used the tag.',
  '- Exact model digests, request/document hashes, schemas and native binary hashes are in the raw artifacts and audited analysis.',
  '', 'The [evidence archive](evidence.zip) preserves the original fifteen GitHub artifact ZIPs, with their GitHub SHA-256 digests in INDEX.json. [audit.json](audit.json) and [replay-audit.json](replay-audit.json) passed. [detailed-analysis.json](detailed-analysis.json) contains the full metrics and calibration observations. Rebuild this report with python experiments/service-understanding/reproduce_report.py after installing the project.']
 (out/'REPORT.md').write_text('\n'.join(lines)+'\n')
 (out/'detailed-analysis.json').write_text(json.dumps({'models':data,'manifests':manifests,'infrastructure':infrastructure,'registry':registry,'identities':identities,'native_replay':native_replay,'one_replay':one_replay},indent=2))
 if not data:raise RuntimeError('No model observations; no numerical report available')

if __name__=='__main__':main()
