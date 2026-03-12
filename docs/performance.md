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

## Historical trend guidance

For trend tracking across releases:

1. Persist each benchmark JSON and gate report artifact in CI.
2. Compare new runs against the previous release and against threshold baselines.
3. Plot time-series per stable profile id (not just global medians).
4. Flag sustained drift (3+ runs) even if the gate still passes.
5. Re-baseline thresholds only after documenting hardware/runtime deltas.
