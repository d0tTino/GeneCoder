# FEC Benchmarks

GeneCoder provides a CLI subcommand to benchmark forward error correction implementations.
Internally it reuses `benchmarks/fec_bench.py` which loads FEC plugins, encodes sample data,
introduces random bit flips and reports encode/decode throughput along with the residual bit error rate.

Run with default settings (1&nbsp;MB input, 1% bit flip probability):

```bash
python -m genecoder.cli benchmark fec --format csv > results.csv
```

Use `--format json` to emit JSON instead of CSV, `--output` to write to a file and
`--plot` to save a PNG chart of the results generated with `genecoder.report`.

## Quick Tutorial

To quickly test the benchmark script with minimal data run:

```bash
python -m genecoder.cli benchmark fec --size 16 --error-prob 0 --format csv
```

which prints a CSV table similar to:

```text
fec,encode_mb_s,decode_mb_s,ber,error
bch,,,,bchlib is required for BCH encoding. Install it via 'pip install bchlib'.
fountain,,,,pyfinite is required for Fountain encoding. Install it via 'pip install pyfinite'.
```

Generating JSON output uses the same flags with `--format json`:

```bash
python -m genecoder.cli benchmark fec --size 16 --error-prob 0 --format json
```

Example JSON:

```json
[
  {"fec": "bch", "error": "bchlib is required for BCH encoding. Install it via 'pip install bchlib'."},
  {"fec": "fountain", "error": "pyfinite is required for Fountain encoding. Install it via 'pip install pyfinite'."}
]
```
