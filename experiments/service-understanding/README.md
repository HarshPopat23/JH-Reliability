# Service understanding experiment

Question: does accurate external-service documentation improve model decisions, compared with basic, missing, misleading or stale contracts?

The completed experiment uses real Qwen3 4B Instruct and Gemma3 1B through Ollama, seven documentation conditions, native Blaze, and actual One containers. See [the audited report](../../results/service-understanding-final/REPORT.md) and [execution status](EXECUTION-STATUS.md). Neither model is assumed calibrated.

## Reproduce the report without inference or Docker

From the repository root with Python 3.12:

```sh
python -m pip install -e '.[dev]'
python experiments/service-understanding/reproduce_report.py
```

This verifies the original artifact digests, reconstructs both complete model corpora, audits request hashes and replay verdicts, and produces `results/service-understanding-reproduced/REPORT.md`. No model requests occur. The evidence archive preserves original ZIP bytes, including the initially generated strict-score reports.

## Run fresh experiments

The workflows are `service-understanding.yml` (actual model inference and matched gateway branches), `service-understanding-replay.yml` (native saved-body audit), and `service-understanding-one-replay.yml` (actual One HTTP evaluation/trace audit). The replay workflows pin the completed source run; update their run ID deliberately when studying new model data. All support manual workflow dispatch. Builds and inference can take significant CPU time.

For local inference, compile `experiments/hosted-sourcemeta/worker.cc`, start One with the three versioned study schemas, start Ollama and pull the required models. Set `ACLAB_BLAZE_WORKER` to the native executable and `ONE_URL` to the actual service. Then:

```sh
python experiments/service-understanding/study.py --model qwen3:4b-instruct --tasks 24 --repeats 5 --output results/new-qwen
python experiments/service-understanding/study.py --model gemma3:1b --tasks 24 --repeats 5 --output results/new-gemma
```

The existing report is a synthetic single-action pilot. Correct request bodies, actual execution, runtime contract rejection and backend semantic checks are separate outcomes. The post-hoc scoring correction and substantial Qwen abstention must be disclosed when sharing it.
