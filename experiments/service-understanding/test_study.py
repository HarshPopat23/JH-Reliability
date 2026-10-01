import importlib.util
from pathlib import Path
from jsonschema import Draft202012Validator

spec = importlib.util.spec_from_file_location('service_study',Path(__file__).with_name('study.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def test_backend_security_and_concurrency():
 assert all(m.probes().values())

def test_schema_valid_can_be_semantically_wrong():
 t = m.tasks()[0]; body = {**t['gold'],'value':1}
 assert Draft202012Validator(m.contract(t['family'])).is_valid(body)
 b = m.Backend(t)
 assert b.execute(body)[0] == 422
 assert b.writes == 0

def test_version_contracts_are_distinct():
 assert m.digest(m.contract('refund',1)) != m.digest(m.contract('refund',2))
 assert not Draft202012Validator(m.contract('refund',2)).is_valid({**m.tasks()[0]['gold'],'expected_version':1})

def test_every_gold_follows_authoritative_contract():
 for task in m.tasks():
  assert Draft202012Validator(m.contract(task['family'])).is_valid(task['gold'])
  assert m.Backend(task).execute(task['gold'])[0] == 200

def test_calibration_uses_only_development_labels():
 rows = [{'split':split,'probability':.9,'correct_candidate':label,'error':None} for split,label in [('dev',True),('test',False)]]
 result = m.calibration(rows)
 assert result['mapping'][4] == 2/3
 assert result['raw']['brier'] == .81
