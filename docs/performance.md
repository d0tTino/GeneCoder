# Performance Benchmarks

GeneCoder benchmark runs are reproducible and pinned to a frozen corpus payload plus
an explicit scenario matrix in `configs/benchmark_matrix.yaml`.

## Matrix-driven benchmark harness

Benchmark scenarios are defined by a full cross-product of dimensions:

- `codec`
- `simulator`
- `profile`
- `payload_size`

Each scenario in the matrix has a fixed seed to guarantee run-to-run reproducibility.
The benchmark harness lives in `benchmarks/harness.py`, and both public runners now
use that shared harness:

- `benchmarks/throughput.py`
- `benchmarks/error_rate.py`

Run benchmarks from repository root:

```bash
PYTHONPATH=src python benchmarks/throughput.py --format json > throughput.json
PYTHONPATH=src python benchmarks/error_rate.py --format json > error_rate.json
```

## Normalized JSON output contract

Both benchmark runners emit normalized JSON with deterministic schema metadata:

- top-level keys: `benchmark`, `schema_version`, `matrix_version`, `corpus_sha256`, `results`
- per-result keys:
  - `profile`
  - `codec`
  - `simulator`
  - `profile_descriptor`
  - `payload_size`
  - `seed`
  - `substitution_prob`
  - `insertion_prob`
  - `deletion_prob`
  - `dropout_prob`
  - `throughput`
  - `BER`
  - `decode_success`
  - `runtime_per_mb`
  - `encode_mb_s`
  - `decode_mb_s`

This payload is consumed directly by `scripts/evaluate_benchmark_gates.py`.

## Gate evaluation

Baseline snapshots and tolerance gates are centralized in
`configs/benchmark_thresholds.json`.

Evaluate outputs against gates:

```bash
python scripts/evaluate_benchmark_gates.py \
  --benchmark throughput \
  --stdout-file throughput.json \
  --output-json throughput-gate.json

python scripts/evaluate_benchmark_gates.py \
  --benchmark error_rate \
  --stdout-file error_rate.json \
  --output-json error-rate-gate.json
```

Gate reports include pass/fail, per-profile checks, and parsed metrics for audit.

## Benchmark interpretation guidance

When interpreting benchmark outcomes:

1. **Prioritize profile-level comparisons** over aggregate averages.
2. **Read throughput and BER together**; a throughput gain with BER degradation is
   not a win for production quality.
3. **Treat `decode_success` as a hard reliability signal** for clean-profile scenarios.
4. **Use `runtime_per_mb` to detect regressions hidden by small payload runs**.

## Baseline regeneration procedure

When the benchmark matrix or harness logic changes, regenerate threshold baselines:

```bash
PYTHONPATH=src python benchmarks/throughput.py --format json > /tmp/throughput.json
PYTHONPATH=src python benchmarks/error_rate.py --format json > /tmp/error_rate.json
python - <<'PY'
import json
from pathlib import Path

threshold_path = Path("configs/benchmark_thresholds.json")
thresholds = json.loads(threshold_path.read_text(encoding="utf-8"))

for benchmark, artifact in (("throughput", "/tmp/throughput.json"), ("error_rate", "/tmp/error_rate.json")):
    payload = json.loads(Path(artifact).read_text(encoding="utf-8"))
    thresholds[benchmark]["baseline_snapshot"] = {
        result["profile"]: {
            "throughput": round(float(result["throughput"]), 4),
            "BER": round(float(result["BER"]), 6),
            "decode_success": bool(result["decode_success"]),
            "runtime_per_mb": round(float(result["runtime_per_mb"]), 4),
        }
        for result in payload["results"]
    }

threshold_path.write_text(json.dumps(thresholds, indent=2) + "\n", encoding="utf-8")
PY
```

## Historical trend guidance

For trend tracking across releases:

1. Persist each benchmark JSON and gate report artifact in CI.
2. Compare new runs against the previous release and against threshold baselines.
3. Plot time-series per stable profile id (not just global medians).
4. Flag sustained drift (3+ runs) even if the gate still passes.
5. Re-baseline thresholds only after documenting hardware/runtime deltas.
