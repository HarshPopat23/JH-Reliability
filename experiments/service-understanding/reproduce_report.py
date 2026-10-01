"""Rebuild the audited report from the archived, digest-verified artifacts."""
import argparse,hashlib,io,json,subprocess,sys,zipfile
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,default=Path('results/service-understanding-final/evidence.zip'))
 p.add_argument('--work',type=Path,default=Path('results/service-understanding-reproduced-evidence'))
 p.add_argument('--output',type=Path,default=Path('results/service-understanding-reproduced'));a=p.parse_args()
 models=a.work/'models';native=a.work/'native';one=a.work/'one';a.output.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(a.archive) as outer:
  index=json.loads(outer.read('INDEX.json'))
  for item in index:
   data=outer.read(item['archive_member'])
   if hashlib.sha256(data).hexdigest()!=item['digest'].removeprefix('sha256:'):raise RuntimeError('Original artifact digest mismatch')
   name=item['name'];destination=None
   if name.startswith('service-understanding-') and '-shard-' in name:destination=models/name
   elif name=='service-understanding-native-replay':destination=native
   elif name=='service-understanding-live-one-replay':destination=one
   if destination:
    destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as inner:inner.extractall(destination)
 script=Path(__file__).parent
 commands=[['audit.py',str(models),'--output',str(a.output/'audit.json')],
  ['audit_replays.py',str(models),str(native/'replay.jsonl'),str(one/'one-replay.jsonl'),'--output',str(a.output/'replay-audit.json')],
  ['report_evidence.py','--input',str(models),'--output',str(a.output),
   '--native-replay',str(native/'replay-summary.json'),'--one-replay',str(one/'one-replay-summary.json')]]
 for name,*args in commands:subprocess.run([sys.executable,str(script/name),*args],check=True)
 print('Audited report:',a.output/'REPORT.md')

if __name__=='__main__':main()
