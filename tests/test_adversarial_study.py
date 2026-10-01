import asyncio
import importlib.util
import pathlib
import copy
import pytest
from jsonschema import Draft202012Validator
from aclab.types import ExperimentConfig,LabError
from aclab.registry import Registry,Validator

p=pathlib.Path(__file__).resolve().parents[1]/'experiments/adversarial/study.py'
spec=importlib.util.spec_from_file_location('adversarial_study',p);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

def test_labels_are_structurally_valid_but_semantically_different():
 ts=s.tasks();assert len(ts)==60 and len({t['id'] for t in ts})==60
 assert len([t for t in ts if t['split']=='development'])==12
 for t in ts:
  assert Draft202012Validator(s.INPUT).is_valid(t['correct'])
  assert Draft202012Validator(s.INPUT).is_valid(t['dangerous'])
  assert not s.unsafe(t,t['correct'])
  assert s.unsafe(t,t['dangerous'])

@pytest.mark.asyncio
async def test_real_concurrent_cas_conflict_then_recovery_preserves_other_writer():
 t=next(t for t in s.tasks() if t['family']=='state-race');b=s.Backend(t);a=copy.deepcopy(t['correct'])
 with pytest.raises(ValueError,match='VERSION_CONFLICT'):await b.execute(a,'key')
 assert b.race_events and b.state[t['resource_id']]['refunded']==0
 a['expected_version']=2;await b.execute(a,'key')
 r=b.state[t['resource_id']];assert r['refunded']==10 and r['notes']=='Concurrent unrelated note preserved'

@pytest.mark.asyncio
async def test_partial_journal_finishes_without_incrementing_twice():
 t=next(t for t in s.tasks() if t['fault']=='partial-with-journal');b=s.Backend(t);a=t['correct']
 with pytest.raises(TimeoutError):await b.execute(a,'key')
 assert await b.recover(a,'key')
 assert b.state[t['resource_id']]['refunded']==10
 assert await b.execute(a,'key')==b.completed['key']
 assert b.state[t['resource_id']]['refunded']==10

@pytest.mark.asyncio
async def test_unknown_partial_state_does_not_invent_completion():
 t=next(t for t in s.tasks() if t['fault']=='partial-without-journal');b=s.Backend(t)
 with pytest.raises(TimeoutError):await b.execute(t['correct'],'key')
 assert await b.recover(t['correct'],'key') is None
 assert b.state[t['resource_id']]['status']=='open'

def test_policy_and_judge_have_distinct_coverage():
 t=next(t for t in s.tasks() if t['family']=='confirmation' and not t['approved'])
 assert not s.policy(t,t['dangerous'])
 t=next(t for t in s.tasks() if t['family']=='data-leakage' and t['variant']==5)
 assert s.policy(t,t['dangerous']) and s.unsafe(t,t['dangerous'])

def test_blaze_label_requires_an_actual_worker_without_fallback():
 c=ExperimentConfig(validator='blaze');assert c.validator=='blaze'
 with pytest.raises(LabError,match='no fallback'):Validator(Registry(),'blaze',blaze_worker_path='/missing/native-worker')

@pytest.mark.asyncio
async def test_fixture_scoring_is_not_in_task_wall_time(monkeypatch):
 import time
 from aclab.runner import Runner
 from aclab.sandbox import tasks
 import aclab.runner as module
 original=module.labeled_call_safe
 def delayed(*args):time.sleep(.04);return original(*args)
 monkeypatch.setattr(module,'labeled_call_safe',delayed)
 r=Runner(ExperimentConfig(enforcement='policy'))
 start=time.perf_counter();row=await r.run(tasks(1)[0]);wall=(time.perf_counter()-start)*1000
 await r.close()
 assert row['offline_scoring_ms']>=35 and wall-row['latency_ms']>=35
 assert row['validator_engine']=='jsonschema'

@pytest.mark.asyncio
async def test_native_cancellation_reaps_worker_without_fallback(tmp_path):
 import sys
 from aclab.native import NativeBlaze
 fake=tmp_path/'worker'
 fake.write_text('#!'+sys.executable+'\nimport sys,time\nprint(\'{"ready":true}\',flush=True)\nfor line in sys.stdin:time.sleep(30)\n')
 fake.chmod(0o755)
 n=NativeBlaze(Registry(),str(fake));task=asyncio.create_task(n.validate('get_issue','input',{'issue_id':1}))
 while n.process is None:await asyncio.sleep(.005)
 process=n.process;task.cancel()
 with pytest.raises(asyncio.CancelledError):await task
 assert process.returncode is not None and n.process is None and not n.calls
 await n.close()

@pytest.mark.asyncio
async def test_native_rejects_inconsistent_consumed_checksum(tmp_path):
 import sys
 from aclab.native import NativeBlaze
 fake=tmp_path/'worker'
 fake.write_text('#!'+sys.executable+'\nimport sys\nprint(\'{"ready":true}\',flush=True)\nfor line in sys.stdin:print(\'{"valid":true,"iterations":1,"checksum":0}\',flush=True)\n')
 fake.chmod(0o755);n=NativeBlaze(Registry(),str(fake))
 with pytest.raises(LabError,match='no fallback'):await n.validate('get_issue','input',{'issue_id':1})
 assert n.process is None and not n.calls
 await n.close()
