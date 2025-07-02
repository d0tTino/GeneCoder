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
