import importlib.util,pathlib,copy
import pytest,httpx
from jsonschema import Draft202012Validator
p=pathlib.Path(__file__).resolve().parents[1]/'experiments/adversarial-v2/study.py'
spec=importlib.util.spec_from_file_location('adversarial_v2',p);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
def test_fixed_pairs_and_locked_split():
 ts=s.tasks();assert len(ts)==100 and len({t['id'] for t in ts})==100
 assert sum(t['split']=='development' for t in ts)==18
 for t in ts:
  assert Draft202012Validator(s.INPUT).is_valid(t['correct']) and Draft202012Validator(s.INPUT).is_valid(t['dangerous'])
  assert not s.unsafe(t,t['correct']) and s.unsafe(t,t['dangerous'])
def test_approved_recipient_and_private_disclosure():
 for t in s.tasks():
  if t['family']=='data-leakage':
   assert 'approved-auditor@partner.invalid' in t['request']
   a=copy.deepcopy(t['correct']);a['fields']=['notes','summary'] if not t['private_notes'] else ['summary']
   assert not s.unsafe(t,a)
   if t['private_notes']:assert s.policy(t,t['dangerous']) and s.unsafe(t,t['dangerous'])
@pytest.mark.asyncio
async def test_shared_decoder_and_independent_model_identity(tmp_path,monkeypatch):
 import json
 monkeypatch.setattr(s,'OUT',tmp_path);bodies=[]
 def handle(req):
  b=json.loads(req.content);bodies.append(b)
  value={'risk':0,'reason':'safe'} if b['format']==s.JUDGE_SCHEMA else s.args('noop',1)
  return httpx.Response(200,json={'done':True,'done_reason':'stop','message':{'content':json.dumps(value)},'prompt_eval_count':20,'eval_count':20})
 async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
  m=s.Models(client);t=s.tasks()[0]
  await m.infer(s.PLANNER,'same',300);await m.judge(t,t['correct'],None,300);await m.judge(t,t['correct'],None,300,s.SMALL_JUDGE)
 assert bodies[0]['format']==s.INPUT and bodies[1]['model']=='gemma3:4b' and bodies[2]['model']=='gemma3:1b'
 assert s.PLANNER not in (s.JUDGE,s.SMALL_JUDGE)
@pytest.mark.asyncio
async def test_controlled_recovery_coverage_and_nonduplication():
 ts=[t for t in s.tasks() if t['family'] in ('state-race','partial-commit')];assert len(ts)==32
 for t in ts:
  x=await s.recovery_probe(t,'verified-recovery',0)
  assert not x['unsafe_duplicate']
  assert x['goal_success']==(t['fault']!='partial-without-journal')
  if t['fault']=='concurrent-version-change':assert x['race_events'] and x['state']['notes']=='Concurrent unrelated note preserved'
