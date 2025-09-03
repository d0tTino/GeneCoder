# CLI Pipeline Examples

This guide demonstrates common `genecli` commands and sample pipeline
configurations. It covers encoding, channel simulation, decoding and viewing
metrics in the dashboard.

## Basic CLI Flow

```bash
# Encode a sample file with Reed-Solomon FEC
genecli encode --input-files examples/pipeline_demo_input.txt \
  --output-file encoded.fasta --fec reed_solomon

# Run a channel simulation using a configuration file
genecli channel run configs/channel_demo.yaml

# Decode the simulated reads back to the original data
genecli decode --input-files simulated.fasta --output-file decoded.txt

# Launch the Streamlit dashboard to inspect metrics
genecli dashboard examples/illumina_metrics.json
```

## Pipeline Configurations

### Reed–Solomon with Illumina

```yaml
# configs/rs_illumina_pipeline.yaml
# Pipeline using Reed-Solomon FEC with the Illumina simulator.
encode:
  input_files:
    - examples/pipeline_demo_input.txt
  method: base4_direct
  fec: reed_solomon
simulate:
  simulators:
    - illumina
  pipeline:
    illumina_profile: hiseq
decode:
  method: base4_direct
```

Run the pipeline while capturing metrics:

```bash
GENECODER_METRICS_PATH=examples/illumina_metrics.json \
  genecli bundle run configs/rs_illumina_pipeline.yaml
```

### Fountain with Nanopore

```yaml
# configs/fountain_nanopore_pipeline.yaml
# Pipeline using Fountain FEC with the Nanopore simulator.
encode:
  input_files:
    - examples/pipeline_demo_input.txt
  method: base4_direct
  fec: fountain
simulate:
  simulators:
    - nanopore
  pipeline:
    nanopore_profile: r10
decode:
  method: base4_direct
```

Execute with metrics enabled:

```bash
GENECODER_METRICS_PATH=examples/nanopore_metrics.json \
  genecli bundle run configs/fountain_nanopore_pipeline.yaml
```

## Metrics and Troubleshooting

- **Dashboard files** – sample metrics are available at
  [examples/illumina_metrics.json](../examples/illumina_metrics.json) and
  [examples/nanopore_metrics.json](../examples/nanopore_metrics.json).
- **Missing `genecli` command** – ensure the package is installed and on your
  `PATH`.
- **Simulator errors** – install optional dependencies such as `pyfinite`
  for Fountain codes or provide valid profile names like `hiseq` or `r10`.
- **No metrics output** – set `GENECODER_METRICS_PATH` to a writable file
  before running the pipeline.

