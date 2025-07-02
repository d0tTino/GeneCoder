# FEC Benchmarks

GeneCoder ships with `benchmarks/fec_bench.py` for evaluating forward error correction implementations.

The script automatically loads FEC plugins via `FEC_REGISTRY`, encodes sample data,
introduces random bit flips and reports encode/decode throughput along with the residual bit error rate.

Run with default settings (1&nbsp;MB input, 1% bit flip probability):

```bash
PYTHONPATH=src python benchmarks/fec_bench.py --format csv > results.csv
```

Use `--format json` to emit JSON instead of CSV and `--output` to specify an output file.

Results can be plotted using external tools like pandas or matplotlib.

## Quick Tutorial

To quickly test the benchmark script with minimal data run:

```bash
PYTHONPATH=src python benchmarks/fec_bench.py --size 16 --error-prob 0 --format csv
```

which prints a CSV table similar to:

```text
fec,encode_mb_s,decode_mb_s,ber,error
bch,,,,bchlib is required for BCH encoding. Install it via 'pip install bchlib'.
fountain,,,,pyfinite is required for Fountain encoding. Install it via 'pip install pyfinite'.
```

Generating JSON output uses the same flags with `--format json`:

```bash
PYTHONPATH=src python benchmarks/fec_bench.py --size 16 --error-prob 0 --format json
```

Example JSON:

```json
[
  {"fec": "bch", "error": "bchlib is required for BCH encoding. Install it via 'pip install bchlib'."},
  {"fec": "fountain", "error": "pyfinite is required for Fountain encoding. Install it via 'pip install pyfinite'."}
]
```
