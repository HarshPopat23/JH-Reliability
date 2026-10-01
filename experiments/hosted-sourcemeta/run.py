"""Real hosted pilot. No mock providers, no fallback validators, no fabricated costs."""
import asyncio, hashlib, json, os, platform, random, statistics, subprocess, time, traceback
from pathlib import Path
import httpx
from jsonschema import Draft202012Validator
from aclab.registry import Registry, Validator
from aclab.runner import Runner
from aclab.sandbox import tasks
from aclab.types import ExperimentConfig, ProviderConfig, EvaluatorConfig, LabError, canonical, digest
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results'/'real-hosted'; OUT.mkdir(parents=True,exist_ok=True)
WORK=ROOT/'experiments'/'hosted-sourcemeta'/'build'/'bin'/'jh_blaze_worker'
BINPACK=WORK.with_name('jh_binpack')
REG=Registry()
MAN={'evidence_kind':'actual_software_execution','pilot':True,'status':'in_progress','stages':{},'hardware':{'platform':platform.platform(),'cpus':os.cpu_count()},'limits':{'episodes':96,'ollama_requests':800,'repeats':1},'notes':['Authored synthetic workflows, not held-out production traffic.','Baseline retains target ACL, CAS, approval and idempotency.','Local API price is zero; compute, electricity and total cost remain unmeasured.','Native kernel timings exclude parsing and IPC; gateway and IPC timings reported separately.','A passing small parity corpus is not complete JSON Schema specification compliance.']}
def save(name,value): (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False))
def checkpoint(): save('manifest.json',MAN)
def stats(values):
 s=sorted(values)
 return {'n':len(s),'mean':statistics.mean(s),'p50':statistics.median(s),'p95':s[min(len(s)-1,int(.95*len(s)))],'p99':s[min(len(s)-1,int(.99*len(s)))]} if s else None
class Worker:
 def __init__(self,directory):
  self.p=subprocess.Popen([str(WORK),str(directory)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=open(OUT/'blaze-stderr.log','a'),text=True,bufsize=1)
  self.ready=json.loads(self.p.stdout.readline()); assert self.ready.get('ready')
 def call(self,key,instance,n=1):
  start=time.perf_counter_ns(); self.p.stdin.write(key+'\t'+str(n)+'\t'+canonical(instance)+'\n'); self.p.stdin.flush()
  answer=json.loads(self.p.stdout.readline()); answer['ipc_wall_ns']=time.perf_counter_ns()-start
  assert answer['checksum']==(n if answer['valid'] else 0)
  return answer
 def close(self):
  self.p.stdin.close()
  try:self.p.wait(timeout=5)
  except subprocess.TimeoutExpired:self.p.kill();self.p.wait()
class NativeValidator:
 def __init__(self,worker):self.worker=worker;self.calls=[]
 async def validate(self,name,direction,instance):
  start=time.perf_counter_ns()
  try:r=await asyncio.wait_for(asyncio.to_thread(self.worker.call,name+'-'+direction,instance),5)
  except Exception as e:raise LabError('VALIDATOR_UNAVAILABLE','Native Blaze unavailable; no fallback') from e
  self.calls.append({'name':name,'direction':direction,**r,'gateway_wall_ns':time.perf_counter_ns()-start})
  return [] if r['valid'] else ['Native Blaze rejected instance']
def sample(schema):
 if 'enum' in schema:return schema['enum'][0]
 if 'const' in schema:return schema['const']
 t=schema.get('type','object')
 if t=='object':return {k:sample(schema['properties'][k]) for k in schema.get('required',[])}
 if t=='array':return []
 if t=='string':return 'demo'
 if t=='boolean':return True
 if t in ('number','integer'):return max(1,schema.get('minimum',1))
 return None
async def components():
 directory=OUT/'schemas';directory.mkdir(exist_ok=True); transformed=OUT/'transformed';transformed.mkdir(exist_ok=True)
 corpus=[];transform=[]
 for name,c in REG.contracts.items():
  for direction in ('input','output'):
   key=name+'-'+direction;s=c[direction+'_schema'];save('schemas/'+key+'.json',s)
   t=time.perf_counter_ns();p=subprocess.run([str(WORK),'transform',str(directory/(key+'.json'))],capture_output=True,text=True,timeout=30,check=True)
   ts=json.loads(p.stdout);save('transformed/'+key+'.json',ts)
   transform.append({'key':key,'process_wall_ns':time.perf_counter_ns()-t,'changed':digest(s)!=digest(ts),'original_sha':digest(s),'transformed_sha':digest(ts)})
   valid=sample(s)
   cases=[valid,None,[],{'unexpected':True}]
   if isinstance(valid,dict) and valid:
    missing=dict(valid);missing.pop(next(iter(missing)));cases.append(missing)
   for i,x in enumerate(cases):corpus.append({'key':key,'case':i,'instance':x,'expected':Draft202012Validator(s).is_valid(x)})
 save('corpus.json',corpus);save('alterschema.json',transform)
 worker=Worker(directory);tw=Worker(transformed);rows=[]
 try:
  random.Random(42).shuffle(corpus)
  for c in corpus:
   key=c['key'];s=json.loads((directory/(key+'.json')).read_text());py=Draft202012Validator(s)
   for w in (worker,tw):assert w.call(key,c['instance'])['valid']==c['expected'],('PARITY',key,c['case'])
   for round_id in range(10):
    n=2000;start=time.perf_counter_ns();checksum=sum(py.is_valid(c['instance']) for _ in range(n));elapsed=time.perf_counter_ns()-start
    assert checksum==(n if c['expected'] else 0)
    native=worker.call(key,c['instance'],n);trans=tw.call(key,c['instance'],n)
    rows.append({'key':key,'case':c['case'],'round':round_id,'n':n,'python_ns_per_op':elapsed/n,'blaze_ns_per_op':native['engine_ns']/n,'blaze_ipc_wall_ns_batch':native['ipc_wall_ns'],'transformed_ns_per_op':trans['engine_ns']/n,'expected':c['expected'],'consumed_checksum':native['checksum']})
  save('validator-rounds.json',rows)
  MAN['stages']['native_blaze']={'status':'measured','ready':worker.ready,'parity_cases':len(corpus),'rounds':10,'python_ns':stats([r['python_ns_per_op'] for r in rows]),'blaze_ns':stats([r['blaze_ns_per_op'] for r in rows]),'blaze_ipc_batch_ns':stats([r['blaze_ipc_wall_ns_batch'] for r in rows]),'worker_sha256':hashlib.sha256(WORK.read_bytes()).hexdigest()}
  MAN['stages']['alterschema']={'status':'measured','schemas':len(transform),'changed':sum(r['changed'] for r in transform),'parity_cases':len(corpus),'timing_boundary':'process startup plus transform; not in-process transform kernel'}
 finally:worker.close();tw.close()
 bp=[]
 for c in corpus:
  if not c['expected']:continue
  instance=OUT/'binpack-instance.json';instance.write_text(canonical(c['instance']))
  try:
   p=subprocess.run([str(BINPACK),str(directory/(c['key']+'.json')),str(instance)],capture_output=True,text=True,check=True,timeout=30)
   r=json.loads(p.stdout);assert r['correct']==r['rounds'];bp.append({'key':c['key'],'case':c['case'],'json_utf8_bytes':len(canonical(c['instance']).encode()),**r})
  except Exception as e:bp.append({'key':c['key'],'case':c['case'],'error':str(e),'stderr':getattr(e,'stderr',None)})
 save('binpack.json',bp);MAN['stages']['json_binpack']={'status':'measured' if bp and all('error' not in r for r in bp) else 'partial','cases':len(bp),'correct_cases':sum('error' not in r for r in bp),'rows':bp};checkpoint()
async def one():
 async with httpx.AsyncClient(timeout=10,trust_env=False) as client:
  r=await client.get('http://127.0.0.1:8080/self/v1/health');r.raise_for_status()
  validator=Validator(REG,'one','http://127.0.0.1:8080',client);records=[]
  for name,c in REG.contracts.items():
   for direction in ('input','output'):
    key=name+'-'+direction;url='http://127.0.0.1:8080/'+f'lab/{key}.json'
    start=time.perf_counter_ns();r=await client.get(url,headers={'Accept':'application/schema+json'});r.raise_for_status();schema=r.json();fetch_ns=time.perf_counter_ns()-start
    x=sample(c[direction+'_schema']);expected=REG.local_validate(name,direction,x)
    actual=await validator.validate(name,direction,x);assert bool(actual)==bool(expected)
    remote=OUT/'one-schemas';remote.mkdir(exist_ok=True);save('one-schemas/'+key+'.json',schema)
    deps=await client.get(f'http://127.0.0.1:8080/self/v1/api/schemas/dependencies/lab/{key}')
    traces=[]
    for instance in (x,None):
     t=time.perf_counter_ns();tr=await client.post(f'http://127.0.0.1:8080/self/v1/api/schemas/trace/lab/{key}',json=instance);tr.raise_for_status();trace=tr.json()
     assert type(trace.get('valid')) is bool
     traces.append({'instance':instance,'trace':trace,'http_ns':time.perf_counter_ns()-t})
    records.append({'key':key,'fetch_ns':fetch_ns,'schema_sha256':digest(schema),'dependencies_status':deps.status_code,'dependencies_body':deps.text,'traces':traces})
  save('one-verification.json',records)
  # Real container outage: fail closed, no local validator substitution.
  subprocess.run(['docker','pause','jh-one'],check=True,capture_output=True)
  outage=False
  try:
   await validator.validate(next(iter(REG.contracts)),'input',{})
  except LabError as e:outage=e.code=='VALIDATOR_UNAVAILABLE'
  finally:subprocess.run(['docker','unpause','jh-one'],check=True,capture_output=True)
  assert outage
  # Drift test changes trusted expectation, leaving actual live registry unchanged.
  driftreg=Registry();name=next(iter(driftreg.contracts));driftreg.contracts[name]['input_schema']['additionalProperties']=True
  try:await Validator(driftreg,'one','http://127.0.0.1:8080',client).validate(name,'input',{})
  except LabError as e:assert e.code=='REGISTRY_DRIFT'
  else:raise AssertionError('Drift not rejected')
  MAN['stages']['one']={'status':'measured','schemas':len(records),'outage_fail_closed':outage,'drift_rejected':True,'dependencies_all_200':all(x['dependencies_status']==200 for x in records),'note':'Drift: locally approved contract mismatch against unchanged live registry; not runtime refresh test.'};checkpoint()
async def qwen():
 attempts=0;telemetry=[]
 async def record(response):
  nonlocal attempts
  if response.request.url.path=='/api/chat':
   attempts+=1;await response.aread()
   try:
    data=response.json();telemetry.append({k:data.get(k) for k in ['model','created_at','done','done_reason','total_duration','load_duration','prompt_eval_count','prompt_eval_duration','eval_count','eval_duration']})
   except Exception:telemetry.append({'status':response.status_code})
   with (OUT/'qwen-telemetry.jsonl').open('a') as f:f.write(json.dumps(telemetry[-1])+'\n')
 async def cap(request):
  if request.url.path=='/api/chat' and attempts>=800:raise LabError('ATTEMPT_LIMIT','Hosted experiment attempt ceiling reached')
 async with httpx.AsyncClient(timeout=300,trust_env=False,event_hooks={'response':[record],'request':[cap]}) as client:
  show=await client.post('http://127.0.0.1:11434/api/show',json={'model':'qwen3:4b-instruct'});show.raise_for_status();save('qwen-model.json',show.json())
  tags=await client.get('http://127.0.0.1:11434/api/tags');tags.raise_for_status();save('qwen-tags.json',tags.json())
  provider=ProviderConfig(kind='ollama',model='qwen3:4b-instruct',base_url='http://127.0.0.1:11434',timeout_s=300,max_tokens=384,temperature=0,extra_body={'think':False,'keep_alive':-1,'options':{'num_predict':384,'num_ctx':8192,'num_thread':4,'temperature':0,'seed':42}})
  arms=[('baseline','baseline','python',False),('schema-python','schema','python',False),('policy-python','policy','python',False),('policy-blaze','policy','blaze',False),('policy-one-fetch-blaze','policy','one-fetch',False),('policy-one-http','policy','one-http',False),('policy-alterschema-blaze','policy','transformed',False),('full-one-alterschema-blaze','full','transformed',True)]
  selected=[tasks(72)[i] for i in (0,1,2,5,6,7,8,9,10,37,49,61)]
  save('task-manifest.json',[{'id':t.id,'category':t.category,'fault':t.fault} for t in selected]);save('model-settings.json',provider.model_dump())
  # Warmup real inference is excluded from episode statistics but included in attempt counts.
  warm=await client.post('http://127.0.0.1:11434/api/chat',json={'model':provider.model,'messages':[{'role':'user','content':'Reply OK.'}],'stream':False,'think':False,'options':provider.extra_body['options'],'keep_alive':-1});warm.raise_for_status()
  runners={};workers=[];validations={};rows=[];startup={}
  try:
   for arm,enforcement,engine,full in arms:
    start=time.perf_counter_ns();config=ExperimentConfig(provider=provider,enforcement=enforcement,evaluator=EvaluatorConfig(kind='llm',planner=provider) if full else EvaluatorConfig(kind='none'),validator='one' if engine=='one-http' else 'jsonschema',docs='recovery',concurrency=1,repeats=1,max_steps=6,episode_timeout_s=900,cache='off')
    runner=Runner(config,client=client)
    if engine=='one-fetch' or full:
     # Fetch/hash-pin all schemas via real One before compiling locally.
     v=Validator(runner.registry,'one',client=client)
     for name,c in runner.registry.contracts.items():
      for direction in ('input','output'):await v.validate(name,direction,sample(c[direction+'_schema']))
    if engine in ('blaze','one-fetch','transformed'):
     directory=OUT/('transformed' if engine=='transformed' else 'one-schemas' if engine=='one-fetch' else 'schemas')
     worker=Worker(directory);workers.append(worker);nv=NativeValidator(worker);runner.validator=runner.gateway.validator=nv;validations[arm]=nv
    runners[arm]=runner;startup[arm]=time.perf_counter_ns()-start
   # Interleave random arm order per task to reduce CPU/time drift. No concurrency.
   rng=random.Random(42)
   for task in selected:
    order=list(runners);rng.shuffle(order)
    for arm in order:
     runner=runners[arm];before=len(validations[arm].calls) if arm in validations else 0
     row=await runner.run(task);row['arm']=arm;row['validator_engine']=dict((a,e) for a,_,e,_ in arms)[arm];row['startup_ns_excluded']=startup[arm]
     if arm in validations:row['native_validation_calls']=validations[arm].calls[before:]
     rows.append(row)
     with (OUT/'episodes.jsonl').open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
     print(json.dumps({'task':task.id,'arm':arm,'safe_success':row['safe_success'],'seconds':round(row['latency_ms']/1000,2),'attempts':attempts}),flush=True)
     MAN['stages']['qwen']={'status':'in_progress','completed':len(rows),'planned':96,'attempts':attempts};checkpoint()
     if attempts>=800:raise RuntimeError('Inference budget exhausted')
  finally:
   for worker in workers:worker.close()
   for runner in runners.values():await runner.close()
  summary=[]
  for arm,_,_,_ in arms:
   rs=[r for r in rows if r['arm']==arm]
   summary.append({'arm':arm,'episodes':len(rs),'safe_success':sum(r['safe_success'] for r in rs),'unsafe_actions':sum(r['unsafe_actions'] for r in rs),'errors':sum(bool(r['error']) for r in rs),'latency_ms':stats([r['latency_ms'] for r in rs]),'model_calls':sum(r['model_calls'] for r in rs),'input_tokens':sum(r['input_tokens'] for r in rs) if all(r['input_tokens'] is not None for r in rs) else None,'output_tokens':sum(r['output_tokens'] for r in rs) if all(r['output_tokens'] is not None for r in rs) else None,'cost_usd':None})
  save('qwen-summary.json',summary);MAN['stages']['qwen']={'status':'measured','completed':len(rows),'planned':96,'attempts':attempts,'summary':summary};checkpoint()
async def main():
 for name,function in [('components',components),('one',one),('qwen',qwen)]:
  try:await function()
  except Exception as e:
   MAN['stages'][name]={'status':'failed','error':str(e),'traceback':traceback.format_exc()};checkpoint();print(traceback.format_exc(),flush=True)
   if name=='components':break
 MAN['status']='complete' if all(MAN['stages'].get(n,{}).get('status')=='measured' for n in ('native_blaze','one','alterschema','json_binpack','qwen')) else 'partial';checkpoint()
if __name__=='__main__':asyncio.run(main())
