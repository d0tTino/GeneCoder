# Performance Benchmarks

GeneCoder includes a small benchmark script measuring encoding and decoding throughput.
Run the benchmark from the repository root:

```bash
PYTHONPATH=src python benchmarks/throughput.py
```

Sample output on a GitHub Codespace instance:

```
Base-4     encode: 2.6 MB/s  decode: 1.5 MB/s
Huffman    encode: 1.3 MB/s  decode: 0.6 MB/s
GC-balanced encode: 0.7 MB/s  decode: 1.1 MB/s
```

These numbers were produced using 1&nbsp;MB random inputs and will vary by hardware.

The repository also includes `benchmarks/error_rate.py` which measures decoding accuracy.
It encodes 1&nbsp;MB of random data, introduces 1% substitution errors,
decodes the noisy sequence and reports encoding/decoding throughput along with the computed bit error rate (BER).
Run it as:

```bash
PYTHONPATH=src python benchmarks/error_rate.py
```

Sample output:

```
encode: 2.6 MB/s  decode: 1.5 MB/s  BER: 0.0098
```

Actual numbers will depend on your machine and Python version.

## CI gate automation for phase transitions

Benchmark gate thresholds are centralized in
`configs/benchmark_thresholds.json` and evaluated by
`scripts/evaluate_benchmark_gates.py` so updates are intentional and reviewed
in one place. Alignment to roadmap/capability gate definitions is validated by
`scripts/check_benchmark_gate_alignment.py`.

The Python CI workflow runs both benchmark commands and evaluates them against
the phase-gate thresholds defined in `docs/development_roadmap.md` and
`docs/capabilities.yaml`:

- Throughput gate (Phase 2 -> Phase 3):
  `PYTHONPATH=src python benchmarks/throughput.py`
- BER gate (Phase 3 -> Phase 4):
  `PYTHONPATH=src python benchmarks/error_rate.py`

Each run publishes artifacts for auditability:

- Throughput job artifact `benchmark-throughput` with:
  - `artifacts/benchmarks/throughput.stdout`
  - `artifacts/benchmarks/throughput-gate.json`
- BER job artifact `benchmark-error-rate` with:
  - `artifacts/benchmarks/error_rate.stdout`
  - `artifacts/benchmarks/error_rate-gate.json`

You can run a local gate check with:

```bash
PYTHONPATH=src python benchmarks/throughput.py > throughput.stdout
python scripts/evaluate_benchmark_gates.py \
  --benchmark throughput \
  --stdout-file throughput.stdout \
  --output-json throughput-gate.json
```

To verify thresholds and documentation stay in sync locally:

```bash
python scripts/check_benchmark_gate_alignment.py
```
