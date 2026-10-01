import json
from pathlib import Path
from study import INPUT,OUTPUT,tasks,ROOT
p=ROOT/'experiments/adversarial/infra/one'
(p/'schemas').mkdir(parents=True,exist_ok=True)
for d,s in [('input',INPUT),('output',OUTPUT)]:
 (p/'schemas'/f'action-{d}.json').write_text(json.dumps(s))
(p/'one.json').write_text(json.dumps({'url':'http://127.0.0.1:8080','html':{'name':'Adversarial action schemas'},'contents':{'lab':{'title':'Pinned action schemas','path':'./schemas'}}}))
(p/'Dockerfile').write_text('FROM ghcr.io/sourcemeta/one:6.7\nCOPY one.json .\nCOPY schemas schemas\nRUN sourcemeta one.json\n')
(ROOT/'experiments/adversarial/tasks.json').write_text(json.dumps(tasks(),indent=2))
