"""Build combined report from actually downloaded model artifacts only."""
import argparse
import json
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',default='combined-evidence');p.add_argument('--output',default='results/service-understanding-comparison');args=p.parse_args()
 root=Path(args.input);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
 analyses=[json.loads(path.read_text()) for path in root.rglob('analysis.json') if 'offline' not in str(path) and 'preflight' not in str(path)]
 unique={a['manifest']['model']:a for a in analyses}
 lines=['# Multi-model service-understanding comparison','','Only completed/partial artifact measurements are reported. Synthetic first-action pilot; confidence calibration remains task-specific.','',
 '| Model | Documentation | Held-out n | Correct | Safe completion | Schema rejects | Backend rejects | p50 ms | p95 ms |',
 '|---|---|---:|---:|---:|---:|---:|---:|---:|']
 for model,a in sorted(unique.items()):
  for r in a['held_out_table']:
   lines.append(f"| {model} | {r['arm']} | {r['n']} | {r['correct']}/{r['n']} | {r['success']}/{r['n']} | {r['schema_rejected']} | {r['backend_rejected']} | {r['p50_ms']:.1f} | {r['p95_ms']:.1f} |")
 lines+=['','## Matched differences','', '| Model | Contrast | Correct candidate difference | 95% task-cluster interval |','|---|---|---:|---|']
 for model,a in sorted(unique.items()):
  for contrast,v in a['paired_contrasts'].items():
   r=v['correct_candidate']
   if r: lines.append(f"| {model} | {contrast} | {100*r['difference']:.1f} pp | [{100*r['ci95'][0]:.1f}, {100*r['ci95'][1]:.1f}] pp |")
 lines+=['','## Raw versus development-calibrated probabilities','','| Model | Probability variant | Test n | Brier | ECE |','|---|---|---:|---:|---:|']
 for model,a in sorted(unique.items()):
  for variant in ['raw','dev_fit_histogram']:
   c=a['calibration'][variant]
   if c: lines.append(f"| {model} | {variant} | {c['n']} | {c['brier']:.4f} | {c['ece']:.4f} |")
 lines+=['','## Limits and interpretation','','Neither Qwen nor Gemma is designated calibrated by assumption. The histogram variant is fitted only on development labels; it does not alter the underlying model or its chosen actions. A lower held-out calibration error is evidence on this corpus, not a safety guarantee. Jev is not run without actual API credentials.',
  '', 'Rich beating poor can reflect additional useful knowledge. Rich beating factual prose suggests presentation benefit within this design. Native validation rejects contract violations; the backend separately rejects semantically wrong but schema-valid actions. No end-to-end gain is attributed to Blaze speed without an engine ablation.',
  '', 'Only 24 tasks across three authored families, five repeats, and twelve test task clusters per model. There is no human-reviewed gold, unseen-family test, equal-token control, large real-service benchmark, or confirmed general calibration. Cached/native infrastructure timings include their stated boundaries. One probes change the approved client URI across already deployed versions, not server hot reload. No monetary cost reduction is established.']
 (out/'REPORT.md').write_text('\n'.join(lines)+'\n');(out/'combined-analysis.json').write_text(json.dumps(unique,indent=2))
 if not unique: raise RuntimeError('No model measurements: no numerical comparison generated')

if __name__=='__main__':main()
