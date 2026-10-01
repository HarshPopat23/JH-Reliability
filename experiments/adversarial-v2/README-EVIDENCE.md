# Expanded adversarial experiment evidence

This report uses real hosted Ollama inference, native Blaze and live One schema distribution. It is an extension with a synthetic in-memory action backend, not a production financial service or the original multistep Runner. The nine-arm matrix retains 100 tasks, five repeats and 4,500 episodes. Independent Gemma judges contribute 2,000 retained fixed-candidate judgments. There are also 480 controlled backend executions.

## Frozen inference sources

- Primary source: `335e0d2c05fbfd1db5f0434acfb04e1da5b9be5b`; [primary run](https://github.com/HarshPopat23/JH-Reliability/actions/runs/36864624343).
- Four-task request repair: `104dcb071a3e870dcfe6c6bf51f95ca487f67569`; [repair run](https://github.com/HarshPopat23/JH-Reliability/actions/runs/36883813313).
- The analysis branch is `experiment/adversarial-report-20261001`. Its frozen task JSON makes the four confirmed refund amounts explicit, matching the repaired inference requests. It does not change policy logic.

The original four requests omitted refund amount although their gold action required 10 credits. We preserve all original observations, replace the affected 180 episodes and 80 judgments with fresh matched inference, and disclose this post-hoc repair. No observations are discarded for model failure. Original and replacement shard manifests are both retained.

## Bundle layout

Extract the evidence ZIP into a checkout of the report branch. The resulting root directories must be `expanded-evidence/` and `expanded-report/`.

- `expanded-evidence/original-zips/`: 24 unmodified, digest-verified Actions artifact archives.
- `expanded-evidence/shards/`: 20 original extracted shards, including original ambiguous requests.
- `expanded-evidence/request-repairs/`: four replacement shards.
- `expanded-evidence/*PROVENANCE.json`: Actions artifact IDs and original digests. Recorded download paths are historical; the packaged copies live under `original-zips/`.
- `expanded-evidence/INDEPENDENT-LINK-AUDIT.json`: separately recomputed goals and actual model-call associations.
- `expanded-report/`: retained merged episodes, judgments, controlled recovery, summary metrics, post-hoc policy replay, plots, PDF and Markdown report.
- `SHA256SUMS.txt`: checksums of all packaged data files other than this checksum list itself.

## Reproduce analysis without inference

From the checkout root, with Python 3.11+:

```bash
python experiments/adversarial-v2/analyze_combined.py expanded-evidence/shards --repairs expanded-evidence/request-repairs --output expanded-report
python experiments/adversarial-v2/verify_evidence.py
python experiments/adversarial-v2/replay_policy.py
```

These scripts use the Python standard library and make no model or network calls. `verify_evidence.py` checks all 4,680 raw episode goals and actual inference links plus all 2,080 raw challenge links; the retained analysis uses the repaired set of 4,500/2,000. Bootstrap sampling is fixed and grouped by task. The policy replay first matches all 500 live policy-plus-recovery outcomes, then tests only an export-field predicate correction using equivalent Python logic. The latter is not fresh CEL, Blaze or model inference and provides no latency evidence.

To render the PDF and scientific plots:

```bash
python -m pip install reportlab matplotlib
python experiments/adversarial-v2/build_report.py
```

The PDF renderer uses DejaVu fonts from `/usr/share/fonts/truetype/dejavu/`; install the fonts or adjust the paths on another platform. The retained evidence bundle includes the selected known-safe judge failure examples used by the report.

## Read the conclusion before using the numbers

The current full arm has 18% safe completion versus 68% baseline and about twice its latency. Deterministic enforcement eliminates observed unsafe duplicates; independent judging brings very high false-positive rates. Verified recovery helps, but the current policy also has an operation-field overblocking bug. The suggested correction achieves 92% completion only in post-hoc backend replay, not a fresh live comparison.

All arms share provider JSON-Schema constrained decoding and backend primitive safeguards. One supplies schemas at startup; the full arm evaluates locally using Blaze. One remote HTTP evaluation, diagnostic traces, registry outage and JSON BinPack are separate earlier component evidence, not new measured arms in this matrix. See the [earlier component report](https://github.com/HarshPopat23/JH-Reliability/blob/88d59afe917741e0a5f4e0f077a3adb5b539d114/results/real-hosted/REPORT-COMBINED.md).

Hosted ARM64 CPU timing is not RTX2050 laptop timing. Monetary compute and energy costs were not measured. These uncalibrated Gemma judges do not establish Jev-like calibration or generalization to unseen workflow families. Durable journal recovery, fresh live validation of the corrected CEL predicate, unconstrained-decoder comparisons and production load remain future work. Main was not changed.
