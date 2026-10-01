"""Evidence integrity checks for the corrected sharded pilot."""
import argparse
import importlib.util
import json
from pathlib import Path

spec=importlib.util.spec_from_file_location('study',Path(__file__).with_name('study.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def audit(root):
 models={};issues=[]
 gold={t['id']:t for t in m.tasks()}
 for path in Path(root).rglob('episodes.jsonl'):
  manifest=json.loads(path.with_name('manifest.json').read_text());model=manifest['model']
  if manifest.get('status')!='completed' or manifest.get('completed')!=140:issues.append(f'{model}: incomplete shard manifest')
  infra=json.loads(path.with_name('infrastructure.json').read_text())
  if len(infra.get('one',[]))!=3:issues.append(f'{model}: missing live One fetches')
  for item in infra.get('one',[]):
   if item.get('status')!=200 or item.get('digest')!=m.digest(m.contract(item['family'])):issues.append('One contract digest mismatch')
  if not all(infra.get('deterministic_backend_probes',{}).values()):issues.append('Backend probe failure')
  probe=json.loads(path.with_name('registry-probes.json').read_text())
  if probe.get('status')!='passed':issues.append('Live registry probe failure')
  entry=models.setdefault(model,{'rows':[],'manifests':[],'digests':set()})
  entry['manifests'].append(manifest)
  identities=json.loads(path.with_name('model-identities.json').read_text())
  tag=next((x for x in identities.get('models',[]) if x.get('name')==model or x.get('model')==model),None)
  if tag is None:issues.append(f'{model}: missing exact model identity')
  else:entry['digests'].add(tag['digest'])
  for line in path.read_text().splitlines():
   if not line.strip():continue
   row=json.loads(line);entry['rows'].append(row)
   task=gold[row['task_id']]
   if row['document_sha256']!=m.digest(m.document(task['family'],row['arm'])):issues.append('Documentation hash mismatch')
   prompt='Choose exactly one first API request or abstain. Return the generic envelope. probability_correct estimates whether your proposed body is correct, not confidence in JSON syntax.\n'+m.canonical({'task_id':task['id'],'goal':task['goal'],'resource':task['resource'],'current_version':task['version'],'tenant':'tenant-a','consent':True,'documentation':m.document(task['family'],row['arm'])})
   request={'model':model,'messages':[{'role':'user','content':prompt}],'stream':False,'format':m.ENVELOPE,'keep_alive':-1,'options':{**manifest['settings'],'seed':101+row['repeat'],'num_thread':4}}
   if model.startswith('qwen3'):request['think']=False
   if row['request_sha256']!=m.digest(request):issues.append('Model request hash mismatch')
   if row['native_validator']!=manifest['native']:issues.append('Native identity mismatch')
   if row['native_validator'].get('engine')!='blaze':issues.append('Wrong native engine')
   proposal=row.get('proposal')
   if isinstance(proposal,dict):
    if row['correct_candidate']!=(proposal.get('body')==task['gold']):issues.append('Incorrect candidate gold label')
    if row['safe_success'] and (not row['correct_candidate'] or row.get('api_status')!=200):issues.append('Invalid success label')
   if row['schema_rejected'] and not any(not c['valid'] for c in row['native_calls']):issues.append('Schema rejection without native failure')
   for call in row['native_calls']:
    if call['iterations']!=1 or call['checksum']!=int(call['valid']):issues.append('Unconsumed or invalid native result')
 results={}
 expected={(t['id'],a,r) for t in m.tasks() for a in m.ARMS for r in range(5)}
 for model,entry in models.items():
  keys=[(r['task_id'],r['arm'],r['repeat']) for r in entry['rows']]
  if len(keys)!=len(set(keys)):issues.append(f'{model}: duplicate episodes')
  missing=expected-set(keys)
  if missing:issues.append(f'{model}: {len(missing)} missing episodes')
  if len(entry['digests'])!=1:issues.append(f'{model}: inconsistent model digests')
  results[model]={'episodes':len(keys),'missing':len(missing),'errors':sum(bool(r['error']) for r in entry['rows']),
   'model_digests':sorted(entry['digests']),'commits':sorted({x['commit'] for x in entry['manifests']})}
 if not models:issues.append('No model episodes found')
 return {'passed':not issues,'models':results,'issues':issues}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--output',default='audit.json');a=p.parse_args()
 result=audit(a.root);target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
 if not result['passed']:raise SystemExit(1)
