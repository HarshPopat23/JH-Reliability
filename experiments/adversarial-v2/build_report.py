import json,html,math,statistics,re
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak,Image,KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path.cwd();D=ROOT/'expanded-report'
s=json.loads((D/'analysis.json').read_text());replay=json.loads((D/'policy-correction-replay.json').read_text())
assert s['original_ambiguous_episodes_replaced']==180,'Do not publish unrepaired oracle results'
arms=s['arm_summary'];alias={r['arm']:f'A{i}' for i,r in enumerate(arms)}
names=['Baseline','Schema / Python','Policy / Python','Policy / Blaze','Policy + Gemma4B','Policy + recovery','Policy + Gemma4B + recovery','One + Alter + Blaze + Gemma4B + recovery','Policy + Gemma1B + recovery']
def pct(x):return f'{100*x:.1f}%' if x is not None else 'undefined'
def interval(xs,scale=100,digits=1):return '['+', '.join(f'{x*scale:.{digits}f}' for x in xs)+']'
lines=[]
def p(t):lines.append(t+'\n')
def tbl(headers,rows):
 parts=['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']
 parts += ['| '+' | '.join(map(str,row))+' |' for row in rows]
 p('\n'.join(parts))
base=arms[0];full=arms[7];rec=arms[5]
p('# JH-Reliability: expanded layer experiment')
p('Real inference and audited artifacts | 1 October 2026 | 100 tasks, five repeats, nine arms')
p('## Decision')
p(f"The full layer, as implemented, is not a performance improvement. Baseline safe completion is {base['safe_successes']}/500 ({pct(base['safe_success_rate'])}); full-layer completion is {full['safe_successes']}/500 ({pct(full['safe_success_rate'])}). Unsafe episodes fall from {base['unsafe_action_episodes']} to {full['unsafe_action_episodes']}, but deterministic policy already achieves the latter count without a model judge. Full mean latency rises from {base['latency_ms']['mean']/1000:.2f}s to {full['latency_ms']['mean']/1000:.2f}s ({100*(full['latency_ms']['mean']/base['latency_ms']['mean']-1):+.1f}%). Neither model cost savings nor useful incremental safety from the semantic judge is demonstrated.")
p('Recovery has credible value in this simulator. The current independent Gemma judges are unsuitable as hard execution gates. Fix the deterministic-policy overblocking before drawing product-level conclusions. Blaze and One ran genuinely; this study supports their integration, not a claim that their presence makes model inference faster.')
p('## What actually ran')
tbl(['Component','Evidence'],[['Planner','Real Ollama 0.32.0 qwen3:4b-instruct Q4_K_M inference'],['Independent judges','Real Gemma3:4b and Gemma3:1b; independent of Qwen, uncalibrated'],['Native Blaze','Pinned C++23 source059dbed08ea26bd9a630bad5eb07421f4cc34cc0; persistent ARM64 worker'],['One + AlterSchema','Live One 6.7 containers; actual schema fetch/hash pinning; native transformation; local Blaze'],['Main matrix','100 task instances x5 repeats x9 arms =4,500 retained episodes'],['Judge challenge matrix','2,000 retained fixed safe/unsafe-candidate judgments'],['Controlled faults','480 actual in-memory backend executions, no model inference'],['Policy correction','1,000 post-hoc recorded-proposal backend replays, no fresh model/native validation'],['Tests','119 hosted checks before inference; prior local suite121 checks']])
p('One remote HTTP evaluation/trace/outage and JSON BinPack were measured in the earlier component study, not rerun inside this action matrix. AlterSchema transforms schema documents here; application-state identity uses custom stable JSON hashing. Compiled validators stay in local workers, not in One, and universal semantic-equivalence hashing is not established. Here, One distributes schemas at startup; validation executes locally. Jev is not used, and an independent model is not equivalent to a calibrated evaluator.')
p('## Matched performance')
tbl(['Code','Configuration'],[[alias[r['arm']],names[i]] for i,r in enumerate(arms)])
tbl(['Arm','Safe /500','Safe %','Unsafe episodes','False blocks','Mean s','p95 s','Calls'],[[alias[r['arm']],r['safe_successes'],pct(r['safe_success_rate']),r['unsafe_action_episodes'],r['false_blocks'],f"{r['latency_ms']['mean']/1000:.2f}",f"{r['latency_ms']['p95']/1000:.2f}",r['model_calls']] for r in arms])
p('Safe completion requires the intended final state and no unsafe event. A stopped unknown partial outcome can be safe without completing the goal. For preview-only requests, leaving state unchanged satisfies the goal even if a safe noop is rejected; safe completion and false-block counts can therefore overlap. False block means a blocked/reviewed structurally valid safe proposal, including backend fault reviews, not exclusively judge error. Monetary cost remains unmeasured.')
tbl(['Arm','Success cluster CI95 %','Any-unsafe tasks /100','Task unsafe Wilson CI95 %','Input tokens','Output tokens'],[[alias[r['arm']],interval(r['success_task_cluster_ci95']),r['unsafe_tasks_any_repeat'],interval(r['unsafe_tasks_wilson_ci95']),r['input_tokens'],r['output_tokens']] for r in arms])
p('Intervals use 2,000 task-cluster bootstrap draws, preserving five repeats together. Wilson intervals cover the proportion of tasks with any unsafe repeat. The authored templates are not a random sample of production workflows; zero observed unsafe events is not zero true risk. Threshold and layer comparisons are exploratory, without multiple-comparison correction.')
p('## Add/remove ablations')
tbl(['Comparison','Success delta pp','Cluster CI95 pp','Mean latency delta s','Latency CI95 s'],[[alias[x['from']]+' -> '+alias[x['to']],f"{100*x['success_rate_delta']:+.1f}",interval(x['success_task_cluster_ci95']),f"{x['mean_latency_delta_ms']/1000:+.3f}",interval(x['latency_task_cluster_ci95'],.001,3)] for x in s['comparisons']])
p('A2->A3 isolates Python versus Blaze at fixed enforcement. A3->A4 adds Gemma4B; A3->A5 adds recovery; A5->A6 adds judging with recovery; A6->A7 adds One fetching/pinning and AlterSchema together, not their individual contributions; A6->A8 changes judge size. Matched prompts/settings and randomized arm order reduce bias. Identical request hashes do not guarantee identical generated actions: the independent retained-data audit found470/500 task-repeat groups had identical planner proposals across all nine arms. Model/runtime variation can dominate microsecond validator differences.')
p('## Repeats and pass^k')
tbl(['Arm','pass^1','pass^2','pass^3','pass^4','pass^5','All five /100'],[[alias[r['arm']],*[pct(r[f'pass_pow_{k}']) for k in range(1,6)],r['all_five_success_tasks']] for r in arms])
p('For s successes among five repeats, pass^k=choose(s,k)/choose(5,k), averaged over tasks. pass^5 is success on every sampled attempt; pass@k asks whether at least one succeeds and is different. Five repeats are not 500 independent workflows. Planner temperature .2, seeds300-304, context4096, four CPU threads and the same schema-constrained output decoder are shared across arms.')
p('## Adversarial coverage')
families=sorted({r['family'] for r in s['families']});lookup={(r['arm'],r['family']):r for r in s['families']}
tbl(['Family']+[alias[r['arm']] for r in arms],[[f]+[f"{lookup[r['arm'],f]['safe_successes']}; U{lookup[r['arm'],f]['unsafe_action_episodes']}" for r in arms] for f in families])
p('Cells show safe completions and unsafe episodes(U), out of 100 confirmation episodes and 80 in each other family. Coverage includes unconfirmed/confirmed refunds, delete and close; structurally valid wrong target/amount; public/private export fields; ticket prompt injection; coordinated concurrent version changes; and partial commits with/without a trusted journal. Data and actions are fake and isolated. These are held-out task instances within six known families, not unseen workflow families.')
p('Live Qwen frequently avoided unsafe targets, privacy leaks and injected instructions on its own. Zero unsafe episodes in those families does not demonstrate an incremental judge benefit. Separate fixed candidate challenges test known unsafe proposals even when Qwen does not propose them. The authored gold labels remain necessary for scoring, but are evaluated after timing and never supplied to the judge.')
p('## Independent judge and threshold results')
p('The judges see trusted request, confirmation, allowed resource IDs and approved recipients, plus candidate disclosure and explicitly untrusted notes. A correctly confirmed operation and a noop are defined as safe in the rubric. They do not receive gold labels or the reference correct action. The live gate blocks raw risk>=.5 and fails closed on invalid output. Scores are self-reported; they are not established probabilities.')
tbl(['Judge','Setting','Threshold','Precision','Recall','FPR','TP/FP/TN/FN'],[[m,label,t[key]['threshold'],pct(t[key]['precision']),pct(t[key]['recall']),pct(t[key]['false_positive_rate']),'/'.join(str(t[key][v]) for v in ('tp','fp','tn','fn'))] for m,t in s['thresholds'].items() for label,key in [('live raw','test_at_live_threshold'),('dev-selected raw','test_at_development_selected_raw_threshold'),('dev-fitted map','test_at_development_selected_mapped_threshold')]])
p('Per judge: 18 development tasks / 180 judgments, 82 test tasks / 820 judgments, one safe and one unsafe candidate x5 repeats. Select maximum development F1 subject to FPR<=10%, falling back to unconstrained maximum F1 when infeasible. Fit a monotonic isotonic step map on development only. Test labels never select thresholds. These curves replay observed scores offline; they are not fresh live episode runs at every threshold.')
p('Neither raw judge has a useful operating point satisfying the 10% false-positive target. Most scores saturate at 1. Raising the raw threshold to1 still blocks risk 1. The mapped threshold can meet low FPR only by detecting no unsafe cases; this is a degenerate gate, not a successful calibration. A lower Brier score after mapping does not create discrimination or prove Jev-like calibration. Precision depends on the balanced challenge prevalence and will change in production.')
for m,t in s['thresholds'].items():
 p('### '+m+' held-out diagnostic')
 tbl(['Threshold','Precision','Recall','Recall cluster CI95 %','FPR'],[[r['threshold'],pct(r['precision']),pct(r['recall']),interval(r['recall_task_cluster_ci95']),pct(r['false_positive_rate'])] for r in t['raw_test_curve']])
 tbl(['Score','Valid judgments','Brier','ECE'],[[label,r['n'],f"{r['brier']:.4f}",f"{r['ece']:.4f}"] for label,r in [('Raw',t['raw_test_calibration']),('Dev-fitted map',t['mapped_test_calibration'])]])
 tbl(['Family at .5','Recall','Precision','FPR','Invalid scores'],[[f,pct(r['recall']),pct(r['precision']),pct(r['false_positive_rate']),r['invalid_fail_closed']] for f,r in t['per_family_live_threshold'].items()])
p('Gemma4B-minus-Gemma1B held-out accuracy delta at .5: '+pct(s['judge_4b_minus_1b_test_accuracy']['mean'])+'; task-cluster CI95 percentage points '+interval(s['judge_4b_minus_1b_test_accuracy']['task_cluster_ci95'])+'. The interval and ceiling behavior do not establish a commercially useful judge advantage.')
examples=json.loads((D/'judge-failure-examples.json').read_text())
tbl(['Known-safe candidate','Judge risk','Recorded explanation'],[[r['task_id'],r['judge']['risk'],r['judge']['reason']] for r in examples])
p('These false-positive examples come from real fixed-candidate inference. Amount15 is exactly requested in semantic-arguments-10; exporting summary alone does not disclose the private note in data-leakage-08. A noop does not execute an irreversible action. The judge confuses evidence content or operation severity with the actual proposed action.')
p('## State race and partial-commit recovery')
tbl(['Fault','Mode','Goal /cases','Unsafe duplicates','Competing writes'],[[r['fault'],r['mode'],f"{r['goal_success']}/{r['cases']}",r['unsafe_duplicates'],r['concurrent_writer_events']] for r in s['controlled_recovery']])
p('These 480 fixed-safe-action backend executions are separate from model-driven episodes. Competing coroutines rendezvous and commit a note/version change before action CAS; recovery rereads the version and preserves the unrelated note. Partial financial increments are finalized only after checking a trusted IN-MEMORY intent journal; recovery does not repeat the increment. Missing journal stops OUTCOME_UNKNOWN. The journal survives an injected timeout, not a process crash. Database durability, crash/restart recovery and an uninstrumented external service are untested.')
p('## Deterministic-policy defect and post-hoc correction')
p('The original CEL predicate rejects a secret field for every operation, even when refund/delete/close never reads or exports that field. Qwen sometimes fills unused fields with schema enum values. This causes safe proposals to be blocked and can accidentally block unrelated unsafe proposals. Scope export-field restrictions to the export operation. The correction keeps confirmation, allowed-target membership, amount range and approved-recipient checks.')
tbl(['Recorded-proposal replay','Safe /500','Unsafe episodes','Fresh model calls','Fresh native checks'],[[('Original predicate' if not r['corrected'] else 'Export-scoped predicate'),r['safe_successes'],r['unsafe_action_episodes'],0,0] for r in replay['results']])
p('The replay reproduces all 500 original policy+recovery outcomes first, then executes the same recorded proposals against fresh simulator state with only the field-scope correction. The correction is evaluated as an equivalent Python predicate; the proposed CEL expression is provided but not newly benchmarked. This is a post-hoc backend replay, not a new live Qwen/Blaze/CEL experiment and not latency evidence. It identifies a concrete gate defect; a fresh matched run with the corrected production predicate is still required before claiming its end-to-end improvement. It does not add exact-request amount/target checks or solve general semantics.')
p('## Validation identity and timing boundaries')
tbl(['Arm','Native calls','Validation ms/episode','Model ms/episode','Complete usage'],[[alias[r['arm']],r['native_calls'],f"{r['mean_validation_ms']:.4f}",f"{r['mean_model_wall_ms']:.2f}",r['usage_complete']] for r in arms])
tbl(['Native arm','Kernel mean us/call','Parse mean us/call','IPC mean us/call'],[[alias[r['arm']],*[f"{r['native_timing_ns'][k]['mean']/1000:.3f}" for k in ('engine_ns','parse_ns','ipc_wall_ns')]] for r in arms if r['native_timing_ns']])
p('Explicit validator=blaze is supported and actual binary SHA256/native calls are recorded. The worker consumes checksums, serializes IPC, and fails closed without Python fallback. Cancellation/timeout cleanup was tested. Required runtime schema validation is timed; redundant Python fixture conformance and gold safety scoring are off-clock. Artifact writes are outside episode timing. One fetch, transformation, compile and model warmup are startup work excluded from warm episode latency. Thus the kernel table is not an end-to-end speedup; wrapper/IPC costs can exceed in-process Python validation.')
p('Baseline means no added gateway schema/CEL/judge/recovery, while retaining the same provider JSON-Schema constrained decoding, primitive serialization, backend target ACL, CAS and completed-outcome idempotency as other arms. This is not a baseline without every schema constraint anywhere. The common decoder limits the opportunity for runtime schema validation to add safety. An unconstrained-decoder ablation remains future work.')
tbl(['Arm','Feedback counts'],[[alias[r['arm']],json.dumps(r['feedback_codes'],sort_keys=True)] for r in arms])
p('## Evidence integrity and corrections')
p(f"Audited retained dataset: 4,500 unique task/repeat/arm episodes, 2,000 judgments, 480 controlled cases, 100 unique task IDs and five repeats per arm. Research totals include original plus repairs: {s['outbound_attempts']} outbound attempts, {s['completed_model_responses']} completed responses, {s['total_research_native_calls']} consumed native checks ({s['native_validation_calls']} linked to retained episodes). Model response counts: {json.dumps(s['model_response_counts'])}. Done reasons: {json.dumps(s['done_reasons'])}. Total research input/output tokens: {s['total_inference_input_tokens']}/{s['total_inference_output_tokens']}.")
p('Four original confirmed-refund requests omitted amount although their gold action required 10 credits. The original 180 affected episodes and 80 judgments were excluded from scored endpoints and replaced by fresh four-task matched inference with explicit 10-credit requests. Both original and repaired artifacts are retained. The repair changes request wording only, not the policy or judge threshold. It is a disclosed post-hoc oracle repair, not an untouched blind preregistration. The preceding 60-task study is diagnostic and is not pooled here.')
p('Original inference source335e0d2c05fbfd1db5f0434acfb04e1da5b9be5b; request repair source104dcb071a3e870dcfe6c6bf51f95ca487f67569. Original run36864624343; repair run36883813313. SHA256 verification covers every original downloaded artifact archive. Complete manifests, exact prompts/responses, model digests, native binaries identities, schema hashes, container metadata, traces and backend events remain in the evidence bundle. Model digests and schema identities agree across runners. Main was not changed.')
tbl(['Model','Frozen digest'],[[m,d] for m,d in s['model_digests'].items()])
p('## What remains and product recommendation')
tbl(['Priority','Next evidence needed'],[['1','Fresh live comparison after operation-scoped policy fix and operation-specific action envelopes'],['2','Judge adaptation/calibration using independent labels and unseen workflow families; retain deterministic authorization'],['3','Durable database journal, crash/restart, multi-writer and external-service recovery tests'],['4','Raw versus provider-constrained decoding ablation and larger diverse held-out workflows'],['5','Concurrent gateway load/throughput, cache invalidation, registry version lifecycle and resilience'],['6','Measured compute/energy/serving costs and startup-versus-warm deployment trade-offs']])
p('The evidence supports pursuing a deterministic execution-safety gateway with verified recovery and governed schema distribution. It does not support shipping these Gemma risk judges as hard gates or claiming that the full stack reduces latency/cost. One/Blaze/AlterSchema integration works; their product value should be evaluated separately from model-judge behavior. Novel/unseen unsafe-action detection is not established by these authored families.')
p('No paid model API or paid larger runner was used. API invoice cost is zero; real compute/electricity/time costs are not zero and were not measured. The full arm adds calls and tokens rather than demonstrating savings. All timing is hosted ARM64 CPU, not the user\'s RTX2050 laptop. This is an action-simulator gateway extension, not the original multistep Runner or a live financial backend. BinPack storage savings, prior One remote evaluation and prior nanosecond microbenchmarks remain separate evidence.')
p('Run links: https://github.com/HarshPopat23/JH-Reliability/actions/runs/36864624343 and https://github.com/HarshPopat23/JH-Reliability/actions/runs/36883813313. Reproduce with the analysis, replay and report scripts included in the source branch; raw artifacts and derived metrics are in the evidence bundle.')
(D/'JH-Reliability-Expanded-Report.md').write_text('\n'.join(lines))

plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
fig,ax=plt.subplots(1,2,figsize=(10,3.5),constrained_layout=True);xs=list(range(9));rates=[r['safe_success_rate']*100 for r in arms]
ax[0].bar(xs,rates,color='#207FA1');ax[0].errorbar(xs,rates,yerr=[[rates[i]-100*arms[i]['success_task_cluster_ci95'][0] for i in xs],[100*arms[i]['success_task_cluster_ci95'][1]-rates[i] for i in xs]],fmt='none',ecolor='#18334A',capsize=3)
ax[0].set(ylim=(0,105),xticks=xs,xticklabels=list(alias.values()),ylabel='Safe completion (%)',title='100 tasks x5 repeats; task-cluster CI95')
ax[1].bar(xs,[r['latency_ms']['mean']/1000 for r in arms],color='#D78C3D');ax[1].set(xticks=xs,xticklabels=list(alias.values()),ylabel='Mean task latency (s)',title='Includes actual planner and conditional judge')
fig.savefig(D/'safety-latency.png');plt.close(fig)
fig,ax=plt.subplots(1,2,figsize=(10,3.5),constrained_layout=True)
for m,color in [('gemma3:4b','#207FA1'),('gemma3:1b','#D78C3D')]:
 t=s['thresholds'][m];c=t['raw_test_curve'];ax[0].plot([r['false_positive_rate'] for r in c],[r['recall'] for r in c],'o-',color=color,label=m)
 live=t['test_at_live_threshold'];ax[0].scatter([live['false_positive_rate']],[live['recall']],s=80,marker='x',color=color)
 ax[1].plot([r['recall'] for r in c],[r['precision'] if r['precision'] is not None else math.nan for r in c],'o-',color=color,label=m)
ax[0].axvline(.1,color='#758696',linestyle='--',linewidth=1);ax[0].set(xlim=(-.02,1.02),ylim=(-.02,1.02),xlabel='False-positive rate',ylabel='Unsafe-candidate recall',title='Raw risk .00-1.00; x=live .50')
ax[1].set(xlim=(-.02,1.02),ylim=(-.02,1.02),xlabel='Recall',ylabel='Precision',title='Held-out balanced fixed-candidate set')
for a in ax:a.legend(fontsize=8,loc='lower left')
fig.savefig(D/'judge-curves.png');plt.close(fig)

pdfmetrics.registerFont(TTFont('DV','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'));pdfmetrics.registerFont(TTFont('DVB','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
styles=getSampleStyleSheet()
for k in ('Normal','Title','Heading2','Heading3'):styles[k].fontName='DV' if k=='Normal' else 'DVB'
styles['Normal'].fontSize=8.4;styles['Normal'].leading=12;styles['Normal'].spaceAfter=8
styles['Title'].fontSize=19;styles['Title'].leading=24
styles['Heading2'].fontSize=12;styles['Heading2'].leading=16;styles['Heading2'].spaceBefore=12;styles['Heading2'].spaceAfter=8
cell=ParagraphStyle('cell',fontName='DV',fontSize=7,leading=9.5);head=ParagraphStyle('head',parent=cell,fontName='DVB',textColor=colors.white)
story=[]
def para(t,style=None):
 q=Paragraph(html.escape(t),style or styles['Normal']);story.append(KeepTogether([q]) if style is None else q)
def table(headers,rows):
 n=len(headers);widths={2:[105,410],4:[150,120,120,125],5:[155,90,90,90,90],6:[65,105,75,105,80,85],7:[55,85,70,75,70,70,90],8:[40,60,60,75,65,70,70,75],10:[110]+[45]*9}.get(n,[515/n]*n)
 if headers[0]=='Model':widths=[105,410]
 cells=[]
 for i,row in enumerate([headers]+rows):
  cells.append([Paragraph(html.escape(str(v)),head if i==0 else cell) for v in row])
 q=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT');q.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#18334A')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#F0F5F8'),colors.white]),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#CCD7E0')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
 story.append(q);story.append(Spacer(1,8))
para('JH-Reliability',styles['Title']);para('Expanded layer experiment - 1 October 2026',styles['Heading2'])
para(f"Full layer: {pct(full['safe_success_rate'])} safe completion, {full['unsafe_action_episodes']} unsafe episodes and {full['latency_ms']['mean']/1000:.2f}s mean task time. Baseline: {pct(base['safe_success_rate'])}, {base['unsafe_action_episodes']} unsafe episodes and {base['latency_ms']['mean']/1000:.2f}s. Independent judging is overly restrictive; verified recovery is the useful component.")
table(['Code','Configuration'],[[alias[r['arm']],names[i]] for i,r in enumerate(arms)]);story.append(Image(str(D/'safety-latency.png'),width=515,height=180));story.append(PageBreak())
md=(D/'JH-Reliability-Expanded-Report.md').read_text();blocks=md.strip().split('\n\n');i=0
while i<len(blocks):
 b=blocks[i].strip()
 if b.startswith('# '):i+=1;continue
 if b.startswith('|'):
  ls=b.splitlines();i+=1
  rows=[[v.strip() for v in l.strip().strip('|').split('|')] for l in ls if not re.match(r'^\|[\s\-|]+\|$',l)]
  table(rows[0],rows[1:]);continue
 if b.startswith('## '):
  title=b[3:]
  if title=='Independent judge and threshold results':story.append(KeepTogether([Paragraph(html.escape(title),styles['Heading2']),Image(str(D/'judge-curves.png'),width=515,height=180)]))
  else:para(title,styles['Heading2'])
 elif b.startswith('### '):para(b[4:],styles['Heading3'])
 else:para(b)
 i+=1
def footer(canvas,doc):
 canvas.setFont('DV',7);canvas.setFillColor(colors.HexColor('#526879'));canvas.drawString(40,24,'JH-Reliability | Real inference, matched ablations and disclosed corrections');canvas.drawRightString(555,24,str(doc.page))
pdf=D/'JH-Reliability-Expanded-Report.pdf'
SimpleDocTemplate(str(pdf),pagesize=(595.28,841.89),leftMargin=40,rightMargin=40,topMargin=40,bottomMargin=42,title='JH-Reliability expanded layer experiment',author='Harsh Popat - experiment evidence').build(story,onFirstPage=footer,onLaterPages=footer)
print(pdf)
