# Performance Benchmarks

GeneCoder benchmark runs are reproducible and pinned to a frozen corpus + profile
matrix under `benchmarks/corpus/`:

- `benchmarks/corpus/base_payload.txt`: immutable workload payload.
- `benchmarks/corpus/profiles.json`: benchmark profile matrix (codec, size,
  seed, and mutation rate).

## Reproducible benchmark workflow

Run throughput and BER workloads from the repository root:

```bash
PYTHONPATH=src python benchmarks/throughput.py > throughput.json
PYTHONPATH=src python benchmarks/error_rate.py > error_rate.json
```

Each runner emits standardized JSON for every profile in the matrix. Every
profile result contains the same primary metrics:

- `throughput` (MB/s over encode+decode runtime)
- `BER` (bit error rate)
- `decode_success` (exact payload equality)
- `runtime_per_mb` (seconds per MiB)

The payload also includes corpus metadata (`corpus_version`, `corpus_sha256`) to
prove parity across machines and CI jobs.

## Baseline snapshots and tolerance gates

Baseline snapshots and allowed performance drift are centralized in
`configs/benchmark_thresholds.json`.

- `baseline_snapshot`: frozen per-profile reference values.
- `tolerance_gates`: allowed regression windows (throughput %, BER delta,
  runtime %, decode-success requirement).

Evaluate benchmark outputs against gates:

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

## Competitor-comparable parity methodology

To make external comparisons fair and repeatable:

1. **Fix the workload**: use the exact frozen corpus payload hash and profile
   matrix, including data size and mutation rate.
2. **Normalize metrics**: compare only standardized metrics (`throughput`,
   `BER`, `decode_success`, `runtime_per_mb`) from JSON outputs.
3. **Match profile semantics**: ensure competitor runs use equivalent channel
   noise settings and decoded payload checks.
4. **Use tolerance bands, not single points**: evaluate relative regressions
   versus snapshot baselines to account for machine variance.
5. **Archive artifacts**: persist raw benchmark JSON and gate reports for audit
   trails and reproducibility claims.
