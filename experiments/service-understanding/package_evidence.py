"""Preserve original artifact ZIP bytes with GitHub digest checks."""
import argparse,hashlib,json,zipfile
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--index',type=Path,required=True);p.add_argument('--attachments',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 sources=json.loads(a.index.read_text());paths={}
 for path in a.attachments.rglob('*.zip'):
  data=path.read_bytes();paths.setdefault(hashlib.sha256(data).hexdigest(),path)
 members=[];index=[]
 for source in sources:
  checksum=source['digest'].removeprefix('sha256:')
  if checksum not in paths:raise RuntimeError('Missing exact artifact bytes: '+source['name'])
  path=paths[checksum];data=path.read_bytes()
  if len(data)!=source['size_in_bytes']:raise RuntimeError('Artifact size mismatch')
  members.append((source['name']+'.zip',data));index.append({**source,'archive_member':source['name']+'.zip'})
 expected={f'service-understanding-{m}-shard-{s}' for m in ['qwen','gemma'] for s in range(6)}
 if not expected<=set(x['name'] for x in index):raise RuntimeError('Missing source shards')
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(a.output,'w') as z:
  for name,data in [('INDEX.json',json.dumps(index,indent=2).encode()),*members]:
   info=zipfile.ZipInfo(name,date_time=(2026,10,1,0,0,0));info.compress_type=zipfile.ZIP_STORED;info.external_attr=0o644<<16
   z.writestr(info,data)
 result={'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'bytes':a.output.stat().st_size,'artifacts':len(index)}
 a.output.with_suffix('.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':main()
