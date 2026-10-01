"""Post-hoc native conformance replay; never reclassifies abstention as execution."""
import argparse
import asyncio
import importlib.util
import json
import os
import statistics
from pathlib import Path
from jsonschema import Draft202012Validator
from aclab.native import NativeBlaze

spec=importlib.util.spec_from_file_location('study',Path(__file__).with_name('study.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

async def run(root,out):
 out.mkdir(parents=True,exist_ok=True)
 native=NativeBlaze(m.Registry(),os.environ['ACLAB_BLAZE_WORKER'])
 validators={f:Draft202012Validator(m.contract(f)) for f in m.FAMILIES}
 summary={'scope':'Post-hoc saved-body replay, including abstentions. No new model calls, no task execution, no recovery benefit.','source_run':36907463064,'native':native.identity,'models':{}}
 records=[];keys=set()
 try:
  for f in sorted(root.rglob('episodes.jsonl')):
   manifest=json.loads(f.with_name('manifest.json').read_text());model=manifest['model']
   for line in f.read_text().splitlines():
    if not line.strip():continue
    row=json.loads(line);key=(model,row['task_id'],row['arm'],row['repeat'])
    if key in keys:raise RuntimeError('Duplicate model episode')
    keys.add(key)
    proposal=row.get('proposal');body=proposal.get('body') if isinstance(proposal,dict) else None
    if body is None:continue
    python_valid=validators[row['family']].is_valid(body)
    errors=await native.validate(row['family'],'input',body);call=native.calls[-1]
    if bool(errors)==python_valid:raise RuntimeError('Native/Python validity mismatch')
    records.append({'model':model,'task_id':row['task_id'],'split':row['split'],'arm':row['arm'],'repeat':row['repeat'],
     'body_sha256':m.digest(body),'original_action':proposal.get('action'),'python_valid':python_valid,'native':call})
  for model in sorted({x[0] for x in keys}):
   expected={(model,t['id'],a,r) for t in m.tasks() for a in m.ARMS for r in range(5)}
   if {k for k in keys if k[0]==model}!=expected:raise RuntimeError('Incomplete source coverage')
   rs=[r for r in records if r['model']==model]
   summary['models'][model]={'source_episodes':840,'bodies':len(rs),'accepted':sum(r['native']['valid'] for r in rs),
    'rejected':sum(not r['native']['valid'] for r in rs),'parity_mismatches':0,
    'engine_ns_median':statistics.median(r['native']['engine_ns'] for r in rs),
    'ipc_wall_ns_median':statistics.median(r['native']['ipc_wall_ns'] for r in rs),
    'heldout_by_arm':{a:{'bodies':sum(r['split']=='test' and r['arm']==a for r in rs),
      'rejected':sum(r['split']=='test' and r['arm']==a and not r['native']['valid'] for r in rs)} for a in m.ARMS}}
  summary['ready']=native.ready
 finally:await native.close()
 if len(summary['models'])!=2:raise RuntimeError('Two complete model corpora required')
 (out/'replay.jsonl').write_text(''.join(m.canonical(r)+'\n' for r in records))
 (out/'replay-summary.json').write_text(json.dumps(summary,indent=2))
 print(json.dumps(summary,indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',default='combined-evidence');p.add_argument('--output',default='results/service-understanding-replay');a=p.parse_args()
 asyncio.run(run(Path(a.input),Path(a.output)))
