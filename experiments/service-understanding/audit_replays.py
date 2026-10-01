"""Cross-check actual native and One verdicts against each saved proposal body."""
import argparse,importlib.util,json
from pathlib import Path
from jsonschema import Draft202012Validator
spec=importlib.util.spec_from_file_location('study',Path(__file__).with_name('study.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def audit(root,native,one):
 issues=[];source={};validators={f:Draft202012Validator(m.contract(f)) for f in m.FAMILIES}
 for f in root.rglob('episodes.jsonl'):
  model=json.loads(f.with_name('manifest.json').read_text())['model']
  for line in f.read_text().splitlines():
   r=json.loads(line);p=r.get('proposal')
   if isinstance(p,dict) and p.get('body') is not None:source[(model,r['task_id'],r['arm'],r['repeat'])]=r
 sets=[]
 for kind,path in [('native',native),('one',one)]:
  seen=set()
  for line in path.read_text().splitlines():
   r=json.loads(line);key=(r['model'],r['task_id'],r['arm'],r['repeat'])
   if key in seen:issues.append('Duplicate replay key')
   seen.add(key)
   if key not in source:issues.append('Unexpected replay key');continue
   original=source[key];body=original['proposal']['body'];valid=validators[original['family']].is_valid(body)
   if r['body_sha256']!=m.digest(body):issues.append('Replay body hash mismatch')
   if r['original_action']!=original['proposal']['action']:issues.append('Replay action label mismatch')
   actual=r['native']['valid'] if kind=='native' else r['one_valid']
   if actual!=valid or r['python_valid']!=valid:issues.append('Replay verdict mismatch')
   if kind=='native' and (r['native']['iterations']!=1 or r['native']['checksum']!=int(actual)):issues.append('Unconsumed native verdict')
   if kind=='one' and r['http_status']!=200:issues.append('Invalid HTTP evaluation status')
  if seen!=set(source):issues.append(f'{kind}: incomplete replay coverage')
  sets.append(len(seen))
 return {'passed':not issues,'saved_bodies':len(source),'native_evaluations':sets[0],'one_evaluations':sets[1],'issues':issues}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('native',type=Path);p.add_argument('one',type=Path);p.add_argument('--output',type=Path,default=Path('replay-audit.json'));a=p.parse_args()
 result=audit(a.root,a.native,a.one);a.output.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
 if not result['passed']:raise SystemExit(1)
