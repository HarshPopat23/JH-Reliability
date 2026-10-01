"""Matched documentation-quality pilot. No mock inference or native fallback."""
import argparse
import asyncio
import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
from jsonschema import Draft202012Validator
from aclab.native import NativeBlaze

ARMS = ['none', 'poor', 'moderate', 'rich', 'prose', 'false', 'stale']
FAMILIES = {
 'refund': {'unit': 'minor', 'old_unit': 'major', 'factor': 100,
            'meaning': 'Amounts use minor currency units: 100 minor units equal one major unit.'},
 'schedule': {'unit': 'milliseconds', 'old_unit': 'seconds', 'factor': 1000,
              'meaning': 'Timestamp uses Unix milliseconds, not seconds.'},
 'export': {'unit': 'public_only', 'old_unit': 'all_fields', 'factor': 1,
            'meaning': 'Export only public fields; sensitive fields must never be included.'},
}
BODY = {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'object',
 'required': ['resource', 'value', 'unit', 'expected_version', 'idempotency_key'],
 'additionalProperties': False, 'properties': {
 'resource': {'type': 'string'}, 'value': {'type': 'integer', 'minimum': 0},
 'unit': {'type': 'string'}, 'expected_version': {'type': 'integer', 'minimum': 1},
 'idempotency_key': {'type': 'string', 'minLength': 1}}}
RESPONSE = {'type': 'object', 'required': ['status', 'version'], 'additionalProperties': False,
 'properties': {'status': {'enum': ['done', 'duplicate']}, 'version': {'type': 'integer', 'minimum': 1}}}
ENVELOPE = {'type': 'object', 'required': ['action', 'body', 'probability_correct'],
 'additionalProperties': False, 'properties': {
 'action': {'enum': ['execute', 'abstain']}, 'body': BODY,
 'probability_correct': {'type': 'number', 'minimum': 0, 'maximum': 1}}}

def canonical(x):
 return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(x):
 return hashlib.sha256(canonical(x).encode()).hexdigest()

def tasks():
 out = []
 for family, spec in FAMILIES.items():
  for i in range(8):
   value = 17 + 11*i
   identifier = f'{family}-{i}'
   goal = (f'Refund {value} major currency units' if family == 'refund' else
           f'Schedule at Unix timestamp {1700000000+value} seconds' if family == 'schedule' else
           f'Export the {value} public fields, excluding all sensitive fields')
   target = (1700000000+value)*spec['factor'] if family == 'schedule' else value*spec['factor']
   out.append({'id': identifier, 'family': family, 'split': 'dev' if i%2 == 0 else 'test',
     'goal': goal, 'resource': f'resource-{i}', 'owner': 'tenant-a', 'consent': True,
     'version': 2, 'gold': {'resource': f'resource-{i}', 'value': target,
      'unit': spec['unit'], 'expected_version': 2, 'idempotency_key': identifier}})
 return out

def contract(family, version=2):
 s = json.loads(canonical(BODY))
 s['properties']['unit'] = {'enum': [FAMILIES[family]['unit' if version == 2 else 'old_unit']]}
 s['properties']['expected_version'] = {'const': version}
 return s

def document(family, arm):
 spec = FAMILIES[family]
 facts = {'operation': f'POST /{family}', 'service_version': 2,
  'meaning': spec['meaning'], 'resource': 'Use the resource identifier provided by the user.',
  'expected_version': 'Use the current observed version, which is 2.',
  'idempotency_key': 'Use task_id as the key; reuse it when retrying the same operation.',
  'permission': 'Require ownership and explicit consent; backend checks both.',
  'example': {'resource': 'example-only', 'value': 2500 if family == 'refund' else
              1700000000000 if family == 'schedule' else 3,
              'unit': spec['unit'], 'expected_version': 2, 'idempotency_key': 'example-key'}}
 if arm == 'none': return {'operation': f'POST /{family}'}
 if arm == 'poor':
  basic = json.loads(canonical(BODY))
  for field in basic['properties'].values():
   for key in list(field):
    if key != 'type': del field[key]
  return {'operation': f'POST /{family}', 'schema': basic}
 if arm == 'moderate': return {'operation': f'POST /{family}', 'schema': contract(family)}
 if arm == 'prose':
  # Same rich facts and assertions in prose, without JSON Schema/OpenAPI syntax.
  return '\n'.join([
   f"Operation: POST /{family}. Service version: 2. Request body is required.",
   facts['meaning'], facts['resource'], facts['expected_version'], facts['idempotency_key'], facts['permission'],
   'Request is an object. All five fields are required; no other fields are permitted.',
   'resource: string. value: integer, at least zero.',
   f"unit: exactly the string {spec['unit']}. expected_version: exactly the integer 2.",
   'idempotency_key: string with at least one character.',
   'Example request: '+canonical(facts['example']),
   'Response 200 means completed. Response is an object containing exactly status and version.',
   'status: either done or duplicate. version: integer, at least one.',
   'Request schema dialect: JSON Schema Draft 2020-12. Interface description version: OpenAPI 3.1.0.'
  ])
 version = 1 if arm == 'stale' else 2
 if arm == 'false':
  facts['meaning'] = f"The value uses {spec['old_unit']}; do not convert the supplied value."
 if arm == 'stale':
  facts['service_version'] = 1
  facts['meaning'] = f"This version uses {spec['old_unit']}; values are not scaled."
  facts['expected_version'] = 'Use version 1.'
  facts['example']['unit'] = spec['old_unit']; facts['example']['expected_version'] = 1
 return {'openapi': '3.1.0', 'info': {'title': family, 'version': str(version)},
  'paths': {f'/{family}': {'post': {'description': canonical(facts),
   'requestBody': {'required': True, 'content': {'application/json': {'schema': contract(family, version)}}},
   'responses': {'200': {'description': 'Completed', 'content': {'application/json': {'schema': RESPONSE}}}}}}}}

class Registry:
 def __init__(self):
  self.contracts = {f: {'input_schema': contract(f), 'output_schema': RESPONSE} for f in FAMILIES}
 def get(self, name): return self.contracts[name]

class Backend:
 def __init__(self, task):
  self.task = task; self.version = task['version']; self.ledger = {}; self.writes = 0
  self.lock = threading.Lock()
 def execute(self, body, tenant='tenant-a'):
  with self.lock:
   if tenant != self.task['owner']: return 403, {'error': 'OWNER'}
   if not self.task['consent']: return 403, {'error': 'CONFIRMATION_REQUIRED'}
   if body.get('resource') != self.task['resource']: return 404, {'error': 'WRONG_RESOURCE'}
   key = body.get('idempotency_key')
   if key in self.ledger:
    if self.ledger[key]['body'] != body: return 409, {'error': 'IDEMPOTENCY_CONFLICT'}
    return 200, {'status': 'duplicate', 'version': self.ledger[key]['version']}
   if body.get('expected_version') != self.version: return 409, {'error': 'STATE_RACE'}
   gold = self.task['gold']
   if body.get('value') != gold['value'] or body.get('unit') != gold['unit']:
    return 422, {'error': 'SEMANTIC_MISMATCH'}
   self.writes += 1; self.version += 1
   self.ledger[key] = {'body': body, 'version': self.version}
   return 200, {'status': 'done', 'version': self.version}

class ServiceHandler(BaseHTTPRequestHandler):
 backends = {}
 def log_message(self, *args): pass
 def do_POST(self):
  task_id = self.headers.get('X-Task-ID', '')
  try:
   body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
   code, result = self.backends[task_id].execute(body)
  except (KeyError, ValueError): code, result = 400, {'error': 'INVALID_REQUEST'}
  data = canonical(result).encode(); self.send_response(code)
  self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(data)))
  self.end_headers(); self.wfile.write(data)

def probes():
 t = tasks()[0]; good = t['gold']; results = {}
 b = Backend(t); results['unauthorized'] = b.execute(good, 'tenant-b')[0] == 403 and b.writes == 0
 t2 = {**t, 'consent': False}; b = Backend(t2)
 results['confirmation'] = b.execute(good)[0] == 403 and b.writes == 0
 b = Backend(t); b.version += 1
 results['state_race'] = b.execute(good)[0] == 409 and b.writes == 0
 b = Backend(t); first = b.execute(good); second = b.execute(good)
 results['duplicate_write'] = first[0] == second[0] == 200 and b.writes == 1
 b = Backend(t); codes = []
 threads = [threading.Thread(target=lambda: codes.append(b.execute(good)[0])) for _ in range(16)]
 for thread in threads: thread.start()
 for thread in threads: thread.join()
 results['concurrent_idempotency'] = codes == [200]*16 and b.writes == 1
 results['unexpected_response_python_control'] = not Draft202012Validator(RESPONSE).is_valid({'acknowledged': True})
 return results

def bootstrap(rows, a, b, metric):
 grouped = {}
 for r in rows:
  if r['split'] != 'test': continue
  grouped.setdefault(r['task_id'], {}).setdefault(r['arm'], []).append(float(r[metric]))
 delta = [statistics.mean(v[a])-statistics.mean(v[b]) for v in grouped.values() if a in v and b in v]
 if not delta: return None
 rng = random.Random(913); sims = sorted(statistics.mean(rng.choices(delta, k=len(delta))) for _ in range(2000))
 return {'difference': statistics.mean(delta), 'ci95': [sims[49], sims[1949]], 'task_clusters': len(delta)}

def calibration(rows):
 usable = [r for r in rows if r.get('probability') is not None and not r['error']]
 dev = [r for r in usable if r['split'] == 'dev']; test = [r for r in usable if r['split'] == 'test']
 bins = [(lo, min(1, lo+.2)) for lo in [0, .2, .4, .6, .8]]
 def binid(p): return min(4, int(p*5))
 mapping = {}
 for i in range(5):
  ys = [r['correct_candidate'] for r in dev if binid(r['probability']) == i]
  mapping[i] = (sum(ys)+1)/(len(ys)+2) if ys else (sum(r['correct_candidate'] for r in dev)+1)/(len(dev)+2)
 def measure(calibrated):
  pairs = [(mapping[binid(r['probability'])] if calibrated else r['probability'], int(r['correct_candidate'])) for r in test]
  if not pairs: return None
  diagram = []
  for i, (lo, hi) in enumerate(bins):
   ps = [(p,y) for p,y in pairs if binid(p) == i]
   if ps: diagram.append({'lower': lo, 'upper': hi, 'n': len(ps), 'mean_probability': statistics.mean(p for p,y in ps), 'accuracy': statistics.mean(y for p,y in ps)})
  return {'n': len(pairs), 'brier': statistics.mean((p-y)**2 for p,y in pairs),
   'ece': sum(v['n']*abs(v['mean_probability']-v['accuracy']) for v in diagram)/len(pairs),
   'reliability_bins': diagram,
   'thresholds': [{'threshold': th, 'coverage': sum(p>=th for p,y in pairs)/len(pairs),
    'wrong_accepted': sum(p>=th and not y for p,y in pairs), 'accepted': sum(p>=th for p,y in pairs)} for th in [0,.25,.5,.75,.9,.95]]}
 return {'dev_n': len(dev), 'test_n': len(test), 'raw': measure(False),
  'dev_fit_histogram': measure(True), 'mapping': mapping,
  'limitation': 'Exploratory: synthetic, no human-reviewed labels, shared families, small held-out set; not a calibration guarantee.'}

def summarize(out, rows, manifest):
 test = [r for r in rows if r['split'] == 'test']; table = []
 for arm in ARMS:
  rs = [r for r in test if r['arm'] == arm]
  if not rs: continue
  lat = sorted(r['wall_ms'] for r in rs)
  table.append({'arm': arm, 'n': len(rs), 'correct': sum(r['correct_candidate'] for r in rs),
   'success': sum(r['safe_success'] for r in rs), 'schema_rejected': sum(r['schema_rejected'] for r in rs),
   'backend_rejected': sum(r['backend_rejected'] for r in rs), 'errors': sum(bool(r['error']) for r in rs),
   'confident_wrong': sum(r.get('probability', 0) is not None and (r.get('probability') or 0)>=.9 and not r['correct_candidate'] for r in rs),
   'p50_ms': statistics.median(lat), 'p95_ms': lat[min(len(lat)-1, math.ceil(.95*len(lat))-1)],
   'input_tokens': sum(r['input_tokens'] or 0 for r in rs), 'output_tokens': sum(r['output_tokens'] or 0 for r in rs)})
 contrasts = {f'{a}-{b}': {m: bootstrap(rows,a,b,m) for m in ['correct_candidate','safe_success']} for a,b in [('rich','poor'),('rich','prose'),('false','rich'),('stale','rich')]}
 analysis = {'manifest': manifest, 'held_out_table': table, 'paired_contrasts': contrasts, 'calibration': calibration(rows)}
 (out/'analysis.json').write_text(json.dumps(analysis,indent=2))
 lines = ['# Service understanding pilot report', '', f"Model: `{manifest['model']}`. Status: **{manifest['status']}**.",
  '', 'Synthetic service simulator; single first-action attempt; common decoding and runtime validation. No independently human-verified labels. Neither model is presumed calibrated.', '',
  '| Documentation | Test episodes | Correct candidate | Safe completion | Schema rejects | Backend rejects | Errors | p50 ms | p95 ms |',
  '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
 for r in table:
  lines.append(f"| {r['arm']} | {r['n']} | {r['correct']}/{r['n']} | {r['success']}/{r['n']} | {r['schema_rejected']} | {r['backend_rejected']} | {r['errors']} | {r['p50_ms']:.1f} | {r['p95_ms']:.1f} |")
 lines += ['', '## Attribution and confidence', '', 'Matched task-cluster bootstrap differences and intervals are in analysis.json. Rich-minus-prose uses the same factual content; length and presentation can still differ. Rich/poor differ in information content and length. False/stale documentation tests corruption robustness, not richness alone.', '',
  'Calibration compares raw self-reported correctness probability with development-fit histogram probabilities on test tasks. This postprocessor does not change model choices. Repeats are clustered; there are only twelve held-out tasks across three families. Do not claim general calibration or unseen-service performance.', '',
  '## Component boundaries', '', 'Native Blaze validates runtime requests/responses and logs actual calls/identity. Backend checks enforce state and permission independently. One startup fetch/digest and refresh/outage probes are separate infrastructure evidence. AlterSchema transformation and compile reuse do not imply model-call savings. Correctly shaped but semantically wrong requests may pass Blaze and fail the backend.', '',
  '## Evidence', '', 'See manifest.json, tasks.json, episodes.jsonl, native-calls.json, infrastructure.json and analysis.json. Missing components are blocked, never silently replaced. Monetary inference cost is unknown for local CPU execution; input/output tokens and hardware execution time are available. Real Jev comparison is blocked without credentials.']
 (out/'REPORT.md').write_text('\n'.join(lines)+'\n')

async def run(args):
 out = Path(args.output); out.mkdir(parents=True,exist_ok=True)
 selected = tasks()[:args.tasks]; (out/'tasks.json').write_text(json.dumps(selected,indent=2))
 manifest = {'model': args.model, 'status': 'in_progress', 'planned': len(selected)*len(ARMS)*args.repeats,
  'completed': 0, 'commit': os.getenv('GITHUB_SHA'), 'repeats': args.repeats,
  'task_sha256': digest(selected), 'settings': {'temperature': .2, 'num_ctx': 4096, 'num_predict': 128},
  'native': 'blocked', 'one': 'not_configured', 'jev': 'blocked_no_credentials'}
 native = None; rows = []; infrastructure = {'deterministic_backend_probes': probes()}
 if args.offline:
  infrastructure['inference'] = 'NOT_RUN'; manifest['status'] = 'offline_checks_only'
  manifest['native'] = 'NOT_RUN'; manifest['one'] = 'NOT_RUN'
  (out/'infrastructure.json').write_text(json.dumps(infrastructure,indent=2))
  (out/'manifest.json').write_text(json.dumps(manifest,indent=2)); summarize(out,rows,manifest)
  assert all(infrastructure['deterministic_backend_probes'].values()); return
 worker = os.getenv('ACLAB_BLAZE_WORKER')
 if not worker: raise RuntimeError('Native worker required for live study; no fallback')
 native = NativeBlaze(Registry(),worker); manifest['native'] = native.identity
 server = ThreadingHTTPServer(('127.0.0.1',0),ServiceHandler)
 threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  async with httpx.AsyncClient(timeout=180,trust_env=False) as client:
   tags = await client.get('http://127.0.0.1:11434/api/tags'); tags.raise_for_status()
   (out/'model-identities.json').write_text(json.dumps(tags.json(),indent=2))
   one_url = os.getenv('ONE_URL')
   if one_url:
    fetched = []
    for family in FAMILIES:
     r = await client.get(f'{one_url}/lab/{family}-v2.json'); r.raise_for_status()
     remote = r.json(); remote.pop('$id',None)
     if digest(remote) != digest(contract(family)): raise RuntimeError('Registry drift')
     fetched.append({'family': family, 'digest': digest(remote), 'status': r.status_code})
    manifest['one'] = 'live_fetch_verified'; infrastructure['one'] = fetched
   transforms = []
   for family in FAMILIES:
    p = out/f'{family}-v2.json'; p.write_text(canonical(contract(family)))
    start = time.perf_counter_ns(); tr = subprocess.run([worker,'transform',str(p)],check=True,capture_output=True,text=True)
    transformed = json.loads(tr.stdout)
    transforms.append({'family': family,'input_digest':digest(contract(family)), 'output_digest':digest(transformed), 'wall_ns':time.perf_counter_ns()-start})
    # Explicit request/output probes outside episode timing.
    assert not await native.validate(family,'input',next(t['gold'] for t in selected if t['family']==family))
    assert await native.validate(family,'output',{'acknowledged':True})
   infrastructure['alterschema'] = transforms
   infrastructure['native_ready'] = native.ready
   cached = []
   sample = selected[0]
   for _ in range(100):
    start = time.perf_counter_ns()
    await native.validate(sample['family'],'input',sample['gold'])
    cached.append(time.perf_counter_ns()-start)
   cold = []
   for _ in range(10):
    instance = NativeBlaze(Registry(),worker)
    start = time.perf_counter_ns()
    await instance.validate(sample['family'],'input',sample['gold'])
    cold.append(time.perf_counter_ns()-start)
    await instance.close()
   infrastructure['compiled_cache'] = {'warm_operations':100, 'cold_operations':10,
    'warm_ipc_wall_ns':cached,'fresh_process_compile_ipc_wall_ns':cold,
    'timing_boundary':'Cold includes process startup and compilation; warm includes IPC, parsing and validation. Not an engine-only speedup or decision-cache saving.'}
   native.calls.clear()
   schedule = [(t,a,r) for t in selected for a in ARMS for r in range(args.repeats)]
   random.Random(442).shuffle(schedule)
   for task,arm,repeat in schedule:
    docs = document(task['family'],arm)
    prompt = 'Choose exactly one first API request or abstain. Return the generic envelope. probability_correct estimates whether your proposed body is correct, not confidence in JSON syntax.\n'+canonical({'task_id':task['id'],'goal':task['goal'],'resource':task['resource'],'current_version':task['version'],'tenant':'tenant-a','consent':True,'documentation':docs})
    body = {'model':args.model,'messages':[{'role':'user','content':prompt}], 'stream':False,
     'format':ENVELOPE,'keep_alive':-1,'options':{**manifest['settings'],'seed':101+repeat,'num_thread':4}}
    if args.model.startswith('qwen3'): body['think'] = False
    row = {'task_id':task['id'],'family':task['family'],'split':task['split'],'arm':arm,'repeat':repeat,
     'document_sha256':digest(docs),'request_sha256':digest(body),'error':None,'correct_candidate':False,
     'safe_success':False,'schema_rejected':False,'backend_rejected':False,'probability':None,
     'input_tokens':None,'output_tokens':None,'native_validator':native.identity}
    start = time.perf_counter_ns(); before = len(native.calls)
    try:
     r = await client.post('http://127.0.0.1:11434/api/chat',json=body); r.raise_for_status(); response = r.json()
     row['raw_response'] = response; proposal = json.loads(response['message']['content']); row['proposal'] = proposal
     row['input_tokens'] = response.get('prompt_eval_count'); row['output_tokens'] = response.get('eval_count')
     p = proposal.get('probability_correct')
     if type(p) in (int,float) and math.isfinite(p) and 0<=p<=1: row['probability'] = p
     candidate = proposal.get('body'); row['correct_candidate'] = candidate == task['gold']
     if proposal.get('action') == 'execute':
      if await native.validate(task['family'],'input',candidate): row['schema_rejected'] = True
      else:
       ServiceHandler.backends[task['id']] = Backend(task)
       api = await client.post(f'http://127.0.0.1:{server.server_port}/{task["family"]}',json=candidate,headers={'X-Task-ID':task['id']})
       row['api_status'] = api.status_code; row['api_response'] = api.json()
       if api.status_code != 200: row['backend_rejected'] = True
       elif await native.validate(task['family'],'output',api.json()): row['schema_rejected'] = True
       else: row['safe_success'] = row['correct_candidate']
    except Exception as exc: row['error'] = type(exc).__name__
    row['wall_ms'] = (time.perf_counter_ns()-start)/1e6
    row['native_calls'] = native.calls[before:]; rows.append(row)
    with (out/'episodes.jsonl').open('a') as f: f.write(canonical(row)+'\n')
    manifest['completed'] = len(rows); (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    if len(rows)%20 == 0: print(f"{args.model}: {len(rows)}/{len(schedule)}",flush=True)
   manifest['status'] = 'completed'
 finally:
  server.shutdown(); (out/'native-calls.json').write_text(json.dumps(native.calls,indent=2)); await native.close()
  (out/'infrastructure.json').write_text(json.dumps(infrastructure,indent=2))
  (out/'manifest.json').write_text(json.dumps(manifest,indent=2)); summarize(out,rows,manifest)

if __name__ == '__main__':
 parser = argparse.ArgumentParser(); parser.add_argument('--model',default='qwen3:4b-instruct')
 parser.add_argument('--tasks',type=int,default=24); parser.add_argument('--repeats',type=int,default=5)
 parser.add_argument('--output',default='results/service-understanding'); parser.add_argument('--offline',action='store_true')
 asyncio.run(run(parser.parse_args()))
