"""Post-hoc real One HTTP conformance audit of saved model bodies."""
import argparse,asyncio,importlib.util,json,statistics,time
from pathlib import Path
import httpx
from jsonschema import Draft202012Validator

spec=importlib.util.spec_from_file_location('study',Path(__file__).with_name('study.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

async def run(root,out):
 out.mkdir(parents=True,exist_ok=True);base='http://127.0.0.1:8080'
 report={'scope':'Post-hoc actual One evaluation of saved bodies, including abstentions. No new inference or task execution.','source_run':36907463064,'concurrency':8,'fetch':[],'traces':[],'dependencies':[],'models':{}}
 rows=[];keys=set();validators={f:Draft202012Validator(m.contract(f)) for f in m.FAMILIES}
 async with httpx.AsyncClient(timeout=30,trust_env=False) as client:
  for family in m.FAMILIES:
   r=await client.get(f'{base}/lab/{family}-v2.json');r.raise_for_status();schema=r.json()
   assigned=schema.pop('$id',None)
   if assigned not in [None,f'{base}/lab/{family}-v2']:raise RuntimeError('Unexpected assigned schema identity')
   if m.digest(schema)!=m.digest(m.contract(family)):raise RuntimeError('One contract drift')
   report['fetch'].append({'family':family,'digest':m.digest(schema),'status':r.status_code})
   dep=await client.get(f'{base}/self/v1/api/schemas/dependencies/lab/{family}-v2');dep.raise_for_status()
   report['dependencies'].append({'family':family,'status':dep.status_code,'body':dep.json()})
   gold=next(t['gold'] for t in m.tasks() if t['family']==family)
   for label,body in [('valid',gold),('invalid_unit',{**gold,'unit':'INVALID'})]:
    trace=await client.post(f'{base}/self/v1/api/schemas/trace/lab/{family}-v2',json=body);trace.raise_for_status();tr=trace.json()
    if tr.get('valid')!=(label=='valid'):raise RuntimeError('One trace verdict mismatch')
    report['traces'].append({'family':family,'case':label,'response':tr})
  for f in sorted(root.rglob('episodes.jsonl')):
   model=json.loads(f.with_name('manifest.json').read_text())['model']
   for line in f.read_text().splitlines():
    row=json.loads(line);key=(model,row['task_id'],row['arm'],row['repeat'])
    if key in keys:raise RuntimeError('Duplicate source episode')
    keys.add(key);proposal=row.get('proposal')
    if isinstance(proposal,dict) and proposal.get('body') is not None:rows.append((model,row))
  for model in ['qwen3:4b-instruct','gemma3:1b']:
   expected={(model,t['id'],a,r) for t in m.tasks() for a in m.ARMS for r in range(5)}
   if {k for k in keys if k[0]==model}!=expected:raise RuntimeError('Incomplete model source coverage')
  semaphore=asyncio.Semaphore(8)
  async def evaluate(model,row):
   body=row['proposal']['body'];expected=validators[row['family']].is_valid(body)
   async with semaphore:
    start=time.perf_counter_ns()
    response=await client.post(f'{base}/self/v1/api/schemas/evaluate/lab/{row["family"]}-v2',json=body)
    elapsed=time.perf_counter_ns()-start;response.raise_for_status();verdict=response.json()
   if type(verdict.get('valid')) is not bool or verdict['valid']!=expected:raise RuntimeError('One/Python verdict mismatch')
   return {'model':model,'task_id':row['task_id'],'split':row['split'],'arm':row['arm'],'repeat':row['repeat'],
    'body_sha256':m.digest(body),'original_action':row['proposal'].get('action'),'python_valid':expected,
    'one_valid':verdict['valid'],'one_response':verdict,'http_wall_ns':elapsed,'http_status':response.status_code}
  records=await asyncio.gather(*(evaluate(model,row) for model,row in rows))
  for model in ['qwen3:4b-instruct','gemma3:1b']:
   rs=[r for r in records if r['model']==model];times=sorted(r['http_wall_ns'] for r in rs)
   report['models'][model]={'source_episodes':840,'evaluations':len(rs),'accepted':sum(r['one_valid'] for r in rs),
    'rejected':sum(not r['one_valid'] for r in rs),'parity_mismatches':0,
    'http_ns_p50':statistics.median(times),'http_ns_p95':times[int(.95*(len(times)-1))],
    'http_ns_p99':times[int(.99*(len(times)-1))]}
 (out/'one-replay.jsonl').write_text(''.join(m.canonical(r)+'\n' for r in records))
 (out/'one-replay-summary.json').write_text(json.dumps(report,indent=2))
 print(json.dumps({**report,'traces':'See artifact for full actual diagnostic traces'},indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',default='combined-evidence');p.add_argument('--output',default='results/service-understanding-one-replay');a=p.parse_args()
 asyncio.run(run(Path(a.input),Path(a.output)))
