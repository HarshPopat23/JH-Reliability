"""Live One client version-selection and outage/recovery probes; no server hot-reload claim."""
import concurrent.futures
import hashlib
import json
import subprocess
import time
import urllib.request
from pathlib import Path

URL = 'http://127.0.0.1:8080/lab/'
OUT = Path('results/service-understanding/registry-probes.json')

def fetch(version):
 start = time.perf_counter_ns()
 with urllib.request.urlopen(URL+f'refund-v{version}.json',timeout=5) as r:
  schema = json.load(r)
 return {'version':version,'digest':hashlib.sha256(json.dumps(schema,sort_keys=True).encode()).hexdigest(),
         'wall_ns':time.perf_counter_ns()-start,'schema_version':schema['properties']['expected_version']['const']}

def main():
 report = {'scope':'Both versions deployed in actual One; application switches approved URI. This tests client refresh, not registry in-place hot reload.'}
 try:
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
   pinned = list(pool.map(fetch,[1]*4)); refreshed = list(pool.map(fetch,[2]*4))
  report['pinned_agents'] = pinned; report['refreshed_agents'] = refreshed
  report['refresh_pass'] = all(r['schema_version']==2 for r in refreshed) and all(r['digest']!=pinned[0]['digest'] for r in refreshed)
  subprocess.run(['docker','stop','jh-service-one'],check=True,capture_output=True)
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
   futures = [pool.submit(fetch,2) for _ in range(4)]
   failures = 0
   for future in futures:
    try: future.result()
    except Exception: failures += 1
  report['outage_fail_closed_agents'] = failures
 finally:
  subprocess.run(['docker','start','jh-service-one'],check=True,capture_output=True)
  recovered = None
  for _ in range(30):
   try: recovered = fetch(2); break
   except Exception: time.sleep(1)
  report['recovered'] = recovered
  report['status'] = 'passed' if report.get('refresh_pass') and report.get('outage_fail_closed_agents')==4 and recovered else 'failed'
  OUT.write_text(json.dumps(report,indent=2))
 if report['status'] != 'passed': raise RuntimeError('Registry probe failed')

if __name__ == '__main__': main()
