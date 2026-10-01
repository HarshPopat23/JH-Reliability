import json, pathlib, subprocess, sys, hashlib, time
from jsonschema import Draft202012Validator
from aclab.registry import Registry
from aclab.types import canonical
out=pathlib.Path('results/binpack-followup');out.mkdir(parents=True,exist_ok=True)
binary=pathlib.Path(sys.argv[1]).resolve();assert binary.is_file()
def sample(s):
 if 'enum' in s:return s['enum'][0]
 if 'const' in s:return s['const']
 t=s.get('type','object')
 if t=='object':return {k:sample(s['properties'][k]) for k in s.get('required',[])}
 if t=='array':return []
 if t=='string':return 'demo'
 if t=='boolean':return True
 if t in ('integer','number'):return max(1,s.get('minimum',1))
 return None
rows=[]
for name,c in Registry().contracts.items():
 for direction in ('input','output'):
  key=name+'-'+direction;schema=c[direction+'_schema'];instance=sample(schema);assert Draft202012Validator(schema).is_valid(instance)
  sp=out/(key+'-schema.json');ip=out/(key+'-instance.json');sp.write_text(canonical(schema));ip.write_text(canonical(instance))
  p=subprocess.run([str(binary),str(sp),str(ip)],capture_output=True,text=True,timeout=60,check=True)
  result=json.loads(p.stdout);assert result['correct']==result['rounds']==1000
  rows.append({'key':key,'case':0,'json_utf8_bytes':len(canonical(instance).encode()),**result})
  (out/'binpack.json').write_text(json.dumps(rows,indent=2))
meta={'status':'measured','software':'genuine Sourcemeta JSON BinPack','binary':str(binary),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'cases':len(rows),'roundtrips':sum(r['rounds'] for r in rows),'all_lossless':True,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'compiler_commit':'9c6be797ea4f2a586deff6f871506e7f729f3e8e','bounds':'schema compile/load separate; in-memory encode/decode include stream wrapper construction but exclude parse, binary extraction, JSON equality checks and transport'}
(out/'manifest.json').write_text(json.dumps(meta,indent=2));print(json.dumps({'manifest':meta,'rows':rows},indent=2))
