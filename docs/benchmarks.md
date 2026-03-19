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

To explore how redundancy affects error correction pass one or more `--redundancy`
values. The benchmark will run each FEC backend for every level and report the
resulting bit error rate.

```bash
python -m genecoder.cli benchmark fec --size 1024 --error-prob 0.05 \
    --format json --redundancy 4 8 12
```

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

## External comparison methodology

GeneCoder also tracks a dedicated cross-tool comparison matrix in `benchmarks/competitor_matrix.yaml`.
That matrix uses a versioned schema in `configs/schema/benchmark_competitor_matrix.schema.json`
with the following normalized fields for every scenario:

- `scenario`
- `assumptions`
- `data_source`
- `reproducibility_notes`
- `normalized_outputs`

Each scenario records a GeneCoder reference row plus one or more external baselines. External
entries can come from:

- **Internal reruns**, when the competing tool can be executed in our environment under the same
  payload shape and host constraints.
- **Published-result imports**, when only a paper, supplemental benchmark table, or archived report
  is available. In those cases we normalize the published values into the schema and pin a fixture
  copy so CI can still generate comparison reports offline.

### Fairness constraints

External comparisons should only be included when the benchmark owner confirms:

1. Payload size and corruption model are materially equivalent.
2. Throughput numbers are wall-clock measurements with matching single-thread vs multi-thread
   assumptions.
3. Success/failure semantics use byte-for-byte decode equality or an explicitly documented
   alternative that is called out in `reproducibility_notes`.
4. Any missing metric is expressed through the normalized output notes rather than silently omitted.

### Caveats

- Imported published results may have been collected on different hardware; those comparisons are
  directional rather than absolute.
- Some external tools expose only aggregate tables, so GeneCoder pins fixture baselines for CI and
  notes the original provenance instead of pretending the run is reproducible in-repo.
- CI validates the matrix schema and report generation even when no external executables are
  available by falling back to fixture baselines.
