# CLI Pipeline Examples

This guide demonstrates common `genecli` commands and sample pipeline
configurations. It covers encoding, channel simulation, decoding and viewing
metrics in the dashboard. For deterministic comparisons, review the
[reproducibility checklist](reproducibility.md) before running the examples
below.

## Basic CLI Flow

The multi-oligo pipeline splits the encoded payload into manageable oligos, simulates dropout-heavy sequencing, and stitches the surviving strands back together. The commands below mirror the workflow presented in the repository README.

```bash
# Encode the payload into multiple oligos using streaming mode
genecli encode --input-files examples/pipeline_demo_input.txt \
  --output-file encoded/multi_oligo_stream.fasta --stream --chunk-size 400000

# Run the dropout-aware channel pipeline
genecli channel run configs/channel_multi_oligo.yaml

# Decode the surviving oligos into the original payload
genecli decode --input-files simulated_multi_oligo.fasta --output-file decoded_multi.txt

# Launch the dashboard to inspect dropout, coverage and ECC metrics
genecli dashboard decoded_multi.txt.json
```

## RaptorQ and Fountain via `genecli pipeline`

Run a full encode → simulate → decode pipeline from a single command.
The commands below also write metrics for later inspection.

### RaptorQ FEC

```bash
GENECODER_METRICS_PATH=examples/raptorq_metrics.json \
  genecli pipeline examples/pipeline_demo_input.txt decoded_raptorq.txt \
    --codec base4_direct --fec raptorq \
    --channel illumina --profile hiseq
```

After the run finishes inspect the dropout-aware metrics that accompany the decoded payload:

```bash
jq '.metrics.channel.dropout' decoded_raptorq.txt.json
jq '.metrics.oligo_metrics.coverage_counts' decoded_raptorq.txt.json
jq '.metrics.oligo_metrics.dropout_flags' decoded_raptorq.txt.json
jq '.metrics.sequence_batch.metadata.sim_coverage_histogram' decoded_raptorq.txt.json
jq '.metrics.sequence_batch.metadata.sim_dropout_total' decoded_raptorq.txt.json
```

### Fountain FEC

```bash
GENECODER_METRICS_PATH=examples/fountain_metrics.json \
  genecli pipeline examples/pipeline_demo_input.txt decoded_fountain.txt \
    --codec base4_direct --fec fountain \
    --channel nanopore --profile r10
```

The Fountain pipeline emits the same `sequence_batch` manifest metadata, making it easy to compare per-oligo dropout between
Illumina and Nanopore profiles with a single `jq` invocation. For example:

```bash
jq '.metrics.sequence_batch.metadata.sim_dropout_fraction' decoded_fountain.txt.json
jq '.metrics.oligo_metrics.dropout_flags' decoded_fountain.txt.json
```

**When to choose a scheme**

- **RaptorQ** – optimized for throughput with linear-time algorithms. Internal
  benchmarks show encode/decode speeds in the tens of MB/s with roughly 1.2×
  redundancy. Prefer it for large datasets or when compute time matters.
- **Fountain** – rateless and extremely resilient to erasures but slower
  (single-digit MB/s) with ~1.5× redundancy. Use it when maximal loss tolerance
  outweighs speed.

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
Set `GENECODER_SIM_SEED` (as described in the
[Reproducibility Guide](reproducibility.md#seeding-the-simulation-rng)) and pin
the `illumina_profile` to reproduce the same dropout and quality score sampling
across runs.

### GC-balanced Gold Preset with InSilicoSeq

```yaml
# configs/gold.yaml
# Gold-standard pipeline preset using GC-balanced encoding and Reed-Solomon FEC
# with MiSeq-style Illumina simulation.
encode:
  input_files:
    - tests/data/vertical_slice.txt
  method: gc_balanced
  fec: reed_solomon
simulate:
  simulators:
    - name: insilicoseq
      profile: miseq
  pipeline:
    illumina_profile: miseq
    coverage_distribution:
      18: 1.0
decode:
  method: gc_balanced
```

Run the preset with metrics enabled to mirror the MiSeq 18× coverage and 150 bp
read defaults highlighted in the channel walkthrough:

```bash
GENECODER_METRICS_PATH=examples/gold_metrics.json \
  genecli bundle run configs/gold.yaml
```

`genecli` will prefer the external
[InSilicoSeq](https://github.com/HadrienG/InSilicoSeq) simulator when the
`insilicoseq` CLI is installed. If it is missing, the command transparently
falls back to the built-in Illumina channel while still honouring the MiSeq
profile, coverage and read-length defaults baked into the preset.

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
    dropout_rate: 0.15
decode:
  method: base4_direct
```

Execute with metrics enabled:

```bash
GENECODER_METRICS_PATH=examples/nanopore_metrics.json \
  genecli bundle run configs/fountain_nanopore_pipeline.yaml
```

### DeSP Nanopore Simulation

```yaml
# configs/desp_pipeline.yaml
# Pipeline preset using the external DeSP nanopore simulator with stage-aware
# options. The synthesis pass uses a lower error rate, while the sequencing
# stage mirrors typical R10.4 aggregate errors. Both invocations forward stage-
# specific flags to the binary so manifests capture the provenance.
encode:
  input_files:
    - examples/pipeline_demo_input.txt
  method: base4_direct
  fec: reed_solomon
simulate:
  simulators:
    - name: desp
      stage: synthesis
      error_rate: 0.08
      options:
        - --model
        - r10
    - name: desp
      stage: sequencing
      error_rate: 0.12  # Typical R10.x DeSP runs land between 8–15% aggregate error.
      options: --temperature 5
  pipeline:
    parallel: false
    workers: null
    use_process_pool: false
    use_mpi: false
decode:
  method: base4_direct
```

Install the [DeSP](https://github.com/atcg/deSP) binary and ensure it is on your
`PATH` before running the preset. GeneCoder invokes the simulator once per
stage, forwarding both the stage label and any `options` entries. The resulting
`*.manifest.json` contains a `stages` section summarising the error rates,
options and stage names so downstream analysis can reason about each
invocation.

Run the preset while capturing metrics and writing artefacts to a temporary
bundle cache:

```bash
GENECODER_METRICS_PATH=examples/desp_metrics.json \
  genecli bundle run configs/desp_pipeline.yaml --cache-dir runs/desp
```

If the `desp` executable is missing the adapter falls back to the deterministic
internal Nanopore error model, ensuring the preset still runs for documentation
and CI scenarios.

### Multi-oligo Illumina Dropout Pipeline

The `configs/channel_multi_oligo.yaml` file demonstrates the new dropout-aware channel pipeline. It mixes an Illumina simulator with a coverage distribution and enforces synthesis constraints for the streamed FASTA output.

```yaml
# configs/channel_multi_oligo.yaml
input: encoded/multi_oligo_stream.fasta
output: simulated_multi_oligo.fasta

synthesis:
  min_length: 80
  max_length: 220
  max_homopolymer: 5

simulators:
  - name: illumina
    profile: miseq
    coverage: 18
    read_length: 150

pipeline:
  dropout_rate: 0.12
  coverage_distribution:
    12: 0.25
    16: 0.50
    24: 0.25
  parallel: true
  workers: 4
```

Run the configuration and inspect the emitted `simulated_multi_oligo.fasta.manifest.json` to see per-oligo dropout flags:

```bash
genecli channel run configs/channel_multi_oligo.yaml
genecli html-report --manifest simulated_multi_oligo.fasta.manifest.json \
  --output-file reports/multi_oligo_channel.html
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

