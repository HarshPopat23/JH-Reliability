"""Check the distinction between exact key fidelity and actual goal execution."""
import importlib.util
from pathlib import Path
from copy import deepcopy

spec=importlib.util.spec_from_file_location('report_evidence',Path(__file__).with_name('report_evidence.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def row():
 task=m.m.tasks()[0]
 return {'task_id':task['id'],'proposal':{'action':'execute','body':deepcopy(task['gold'])},
  'api_status':200,'api_response':{'status':'done','version':3},
  'native_calls':[{'direction':'output','valid':True}],
  'without_blaze':{'http_status':200,'response':{'status':'done','version':3},'backend_writes':1}}

def test_valid_alternate_key_is_not_a_failed_goal():
 r=row();r['proposal']['body']['idempotency_key']='example-key'
 assert r['proposal']['body']!=m.GOLD[r['task_id']]['gold']
 assert m.semantic_candidate(r)
 assert m.verified_completion(r) and m.verified_completion(r,True)

def test_semantic_error_or_empty_key_never_counts_as_completion():
 for field,value in [('value',1),('idempotency_key',''),('resource','wrong')]:
  r=row();r['proposal']['body'][field]=value
  assert not m.semantic_candidate(r) and not m.verified_completion(r)

def test_abstention_without_execution_is_not_completion():
 r=row();r['proposal']['action']='abstain';r.pop('api_status');r['without_blaze']=None
 assert m.semantic_candidate(r)
 assert not m.verified_completion(r) and not m.verified_completion(r,True)

def test_success_requires_verified_response_state():
 r=row();r['api_response']['version']=2
 assert not m.verified_completion(r)
 r=row();r['native_calls'][0]['valid']=False
 assert not m.verified_completion(r)
