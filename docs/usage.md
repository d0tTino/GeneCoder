# Usage

## Command-Line Interface (CLI)

See the [Disclaimer](../README.md#disclaimer) before using the toolkit.

For a hands-on introduction check the Jupyter notebooks in the [notebooks/](../notebooks) directory.

GeneCoder operations are performed with the `genecoder` CLI:

```bash
genecli <command> --input-files <path1> [<path2> ...] \
    [--output-file <path>] [--output-dir <dir>] \
    --method <method_name> [--fec <fec_method>] [options]
```

Run `genecli --help` to see all available commands. Use `--offline` to disable
network features and avoid loading cloud integrations:

```bash
genecli --help
```

Example output:

A quick sanity check is to run the command and ensure the usage header appears.

```bash
$ genecli --help | head -n 5
Usage: genecli [-h] [--version] {encode,decode,analyze,channel} ...
GeneCoder: Encode and decode data into simulated DNA sequences.
...
```

If the `genecoder` command isn't found, install the project with Poetry:

```bash
poetry install --no-interaction
```

* `--input-files` – one or more input files.
* `--output-file` – output path for a single input file.
* `--output-dir` – directory for batch operations.
* `--fec` – optional [FEC](glossary.md#forward-error-correction-fec) method (`triple_repeat`, `hamming_7_4`, `reed_solomon`, `ldpc`, `fountain`).
* `--rs-symbol-size` – symbol size (`c_exp`) for Reed‑Solomon FEC. Only relevant with `--fec reed_solomon`.
* `--rs-primitive` – primitive polynomial for Reed‑Solomon FEC (integer or `0x`‑prefixed hex). Only used with `--fec reed_solomon`.
* `--auto-ext` – save encoded files with a `.dna` suffix and decode back to the original extension.
* `--seed` – seed random number generators for reproducible simulations.

See [WORKFLOWS.md](../WORKFLOWS.md) for a step-by-step overview.

### Examples

1. **Encode using Base-4 Direct Mapping**

   ```bash
   genecli encode --input-files path/to/your_document.txt \
       --output-file encoded_base4.fasta --method base4_direct
   ```

2. **Decode using Base-4 Direct Mapping**

   ```bash
   genecli decode --input-files path/to/encoded_base4.fasta \
       --output-file decoded_document.txt --method base4_direct
   ```

3. **Encode with Huffman, parity and Triple-Repeat FEC**

   ```bash
   genecli encode --input-files path/to/my_data.bin \
       --output-dir encoded_output/ --method huffman \
       --add-parity --fec triple_repeat
   ```

4. **Encode using the base6 alphabet**

   ```bash
   genecli encode --input-files data.bin \
       --output-file encoded_base6.fasta --alphabet base6
   ```

   Base5 and base6 are convenience alphabets that map the 2-bit output of
   `base4_direct` to different nucleotide symbols. They do **not** store more
   information per base.

5. **Encode with Base-4 Direct and Hamming(7,4) FEC**

   ```bash
   genecli encode --input-files path/to/important_data.txt \
       --output-dir encoded_hamming/ --method base4_direct --fec hamming_7_4
   ```

6. **Encode with Reed–Solomon FEC**

   ```bash
   genecli encode --input-files path/to/data.bin \
       --output-dir encoded_rs/ --method base4_direct --fec reed_solomon \
       --rs-symbol-size 8 --rs-primitive 0x11d
   ```

7. **Decode a Hamming(7,4) encoded file**

   ```bash
   genecli decode --input-files encoded_hamming/important_data.txt.fasta \
       --output-file decoded_important_data.txt --method base4_direct
   ```

8. **Batch encode multiple files using GC-Balanced**

   ```bash
   genecli encode --input-files file1.txt notes.md image.png \
       --output-dir gc_encoded_batch/ --method gc_balanced \
       --gc-min 0.40 --gc-max 0.60 --max-homopolymer 5
   ```

   The CLI enforces a 45–55% GC window and a maximum homopolymer length of 3 by
   default. The flags above relax those limits for workloads that tolerate
   higher variance.

9. **Batch decode multiple FASTA files**

   ```bash
   genecli decode --input-files gc_encoded_batch/*.fasta \
       --output-dir decoded_batch/ --method gc_balanced
   ```

10. **Stream encode and decode a large file**

   ```bash
   genecli encode --input-files big.bin --output-file big.fasta \
       --stream --method base4_direct
   genecli decode --input-files big.fasta --output-file big_decoded.bin \
       --stream --method base4_direct
   ```

   Streaming operations are **resumable**. Pass `--resume state.json` to
   continue an interrupted encode or decode run.

11. **Introduce channel errors before decoding**

```bash
genecli channel --input-file encoded.fasta --output-file corrupted.fasta \
    --sub-prob 0.02 --ins-prob 0.01 --del-prob 0.01
genecli decode corrupted.fasta --output-file decoded.bin
```

Pass `--seed <int>` to `genecli encode`, `genecli decode`, `genecli channel`, or
`genecli pipeline` to seed random components for reproducible runs.
Alternatively set the `GENECODER_SIM_SEED` environment variable.

### Reproducible pipelines

Setting `GENECODER_SIM_SEED` ensures that every random component—from
constraint fixers to Illumina and Nanopore simulators—uses the same seed.
Running the same encode→channel→decode command twice with the variable set
produces byte‑identical results.

```bash
export GENECODER_SIM_SEED=123
genecli pipeline input.bin out1.bin --codec base4_direct --channel illumina --profile miseq
genecli pipeline input.bin out2.bin --codec base4_direct --channel illumina --profile miseq
cmp out1.bin out2.bin   # files match
```

The same seed works across other profiles, for example Nanopore's `minion`:

```bash
export GENECODER_SIM_SEED=123
genecli pipeline input.bin out1.bin --codec base4_direct --channel nanopore --profile minion
genecli pipeline input.bin out2.bin --codec base4_direct --channel nanopore --profile minion
cmp out1.bin out2.bin   # files match
```

12. **Encode, corrupt and decode a file with automatic extensions**

```bash
genecli encode --input-files hello.jpg --output-dir encoded \
    --method base4_direct --auto-ext
genecli channel --input-file encoded/hello.jpg.dna --output-file corrupted.dna \
    --sub-prob 0.01 --ins-prob 0.01 --del-prob 0.01
genecli decode corrupted.dna --output-dir decoded --auto-ext
```

   Verify the round-trip checksum:

   ```bash
   sha256sum hello.jpg decoded/hello.jpg
   ```

   Add `--checksum` to the encode and decode commands for automatic validation.
13. **Decode using an external simulator**

   The ``--simulator`` option accepts ``d2sim``, ``dnarsim``, ``squigulator`` or
   ``desp``. Install the desired simulator separately and ensure the command is
   on your ``PATH``:

   * ``d2sim`` — [D2Sim](https://github.com/kurimsw/d2sim). Follow the
     instructions in the repository to build the binary and place ``d2sim`` on
     your ``PATH``.
   * ``dnarsim`` — [DNArSim](https://github.com/Purdue-ScottLab/DNArSim)
   * ``squigulator`` — [Squigulator](https://github.com/hasindu2008/squigulator)
   * ``desp`` — [DeSP](https://github.com/atcg/deSP). See the
     [DeSP adapter](simulators.md#desp-adapter) notes for CLI flags and
     environment variables.

   The ``d2sim`` adapter is bundled with GeneCoder and is registered
   automatically. Once the ``d2sim`` command is available you can invoke it with
   ``--simulator d2sim``. The DeSP adapter is loaded in the same way; pass
   additional flags via ``--desp-options`` or by setting
   ``GENECODER_DESP_OPTIONS``.

   When a command is missing GeneCoder automatically falls back to an internal
   error model. For Nanopore presets this means the built-in profiles described
   under [Nanopore fallback profiles](simulators.md#nanopore-fallback-profiles)
   continue to be applied.

   The same simulators can be accessed programmatically via
   ``genecoder.simulators.simulate_reads``.

   ```bash
   genecli decode --input-files encoded.fasta \
       --output-file decoded.bin --simulator squigulator
   ```

14. **Combine simulators into a channel**

   Apply multiple simulators and enforce synthesis constraints:

   ```bash
    genecli channel --input-file encoded.fasta \
        --output-file channel.fasta --simulator simple --simulator indel
    ```

    A built-in Illumina-like model focuses on substitutions and can be
    configured via ``--sub-rate``:

    ```bash
    genecli channel --input-file encoded.fasta \
        --output-file channel.fasta --simulator illumina_builtin --sub-rate 0.01
    ```

    Coverage depth and a base-quality distribution may also be provided:

    ```bash
    genecli channel --input-file encoded.fasta \
        --output-file channel.fasta --simulator illumina_builtin \
        --sub-rate 0.01 --illumina-depth 5 --illumina-quality 0.01,0.02
    ```

   Named sequencing profiles are available:

   - **Illumina** – `miseq`, `hiseq`, `novaseq` (alias `nova`)
   - **Nanopore** – `minion`, `promethion`, `r10`, `r9`, `r10.3`, `r10.4` (see
     [Nanopore fallback profiles](simulators.md#nanopore-fallback-profiles) for
     details on how these presets behave without external binaries)

   List available presets:

   ```bash
   genecli channel list-profiles
   ```

   Example output:

   ```text
   Illumina profiles:
     hiseq
     miseq
     nova
     novaseq

   Nanopore profiles:
     minion
     promethion
     r10
     r10.3
     r10.4
     r9
   ```

   Use `--profile` to apply a preset without specifying a simulator:

   ```bash
   genecli channel --profile miseq --input-file encoded.fasta \
       --output-file channel.fasta
   ```

   For finer control, select a profile with `--illumina-profile`,
   `--nanopore-profile`, or `--indel-profile`. Individual rate options override
   the chosen profile. Custom parameters can also be loaded from YAML files using
   `--illumina-profile-file` or `--nanopore-profile-file`.

   Example end-to-end runs with each preset:

   | Profile | Command |
   | ------- | ------- |
   | miseq | `genecli channel --profile miseq --input-file encoded.fasta --output-file miseq.fasta` |
   | hiseq | `genecli channel --profile hiseq --input-file encoded.fasta --output-file hiseq.fasta` |
   | novaseq | `genecli channel --profile novaseq --input-file encoded.fasta --output-file novaseq.fasta` |
   | minion | `genecli channel --profile minion --input-file encoded.fasta --output-file minion.fasta` |
   | promethion | `genecli channel --profile promethion --input-file encoded.fasta --output-file promethion.fasta` |
   | r10 | `genecli channel --nanopore-profile r10 --input-file encoded.fasta --output-file r10.fasta` |
   | r9 | `genecli channel --nanopore-profile r9 --input-file encoded.fasta --output-file r9.fasta` |
   | r10.3 | `genecli channel --nanopore-profile r10.3 --input-file encoded.fasta --output-file r10_3.fasta` |
   | r10.4 | `genecli channel --nanopore-profile r10.4 --input-file encoded.fasta --output-file r10_4.fasta` |
   | indel illumina | `genecli channel --indel-profile illumina --input-file encoded.fasta --output-file indel_illumina.fasta` |
   | indel nanopore | `genecli channel --indel-profile nanopore --input-file encoded.fasta --output-file indel_nanopore.fasta` |

   **Pair constraint-aware encoders with broadened sequencing presets**

   The broadened Illumina (`hiseq`, `miseq`, `novaseq`) and Nanopore (`r9`,
   `r10`, `r10.3`, `r10.4`, `minion`, `promethion`) presets work well with
   constraint-aware codecs such as `gc_balanced` or `base4_direct` paired with
   explicit guardrails. The snippet below enforces a 40–60% GC window and a
   five-base homopolymer cap while targeting an Illumina NovaSeq-style error
   model:

   ```bash
   genecli encode --input-files payload.bin --output-file encoded_gc_guarded.fasta \
       --method gc_balanced --gc-min 0.40 --gc-max 0.60 --max-homopolymer 5
   genecli channel --profile novaseq --input-file encoded_gc_guarded.fasta \
       --output-file novaseq_guarded.fasta
   genecli decode --input-files novaseq_guarded.fasta --output-file roundtrip.bin
   ```

   Swap in a Nanopore preset to exercise the broadened long-read models while
   keeping the same constraints intact:

   ```bash
   genecli channel --nanopore-profile r10.4 --input-file encoded_gc_guarded.fasta \
       --output-file r10_4_guarded.fasta
   ```

   The generated `.manifest.json` files for the encode and channel steps record
   the GC-content and maximum homopolymer length that were enforced. Open the
   manifest in the dashboard (`genecli dashboard encoded_gc_guarded.fasta.manifest.json`)
   to view the GC/homopolymer gauges alongside coverage and dropout plots.

   Illumina profile files should list `substitution_rate`, `insertion_rate`,
   `deletion_rate`, `coverage`, and `read_length`:

   ```yaml
   substitution_rate: 0.01
   insertion_rate: 0.002
   deletion_rate: 0.003
   coverage: 2
   read_length: 100
   ```

   Nanopore profile files provide `error_rate`, `substitution_rate`,
   `insertion_rate`, `deletion_rate`, and `coverage`:

   ```yaml
   error_rate: 0.15
   substitution_rate: 0.02
   insertion_rate: 0.03
   deletion_rate: 0.04
   coverage: 3
   ```

   The optional `insilicoseq` simulator accepts the same Illumina presets via its
   `--profile` flag, e.g. `--simulator insilicoseq --profile miseq`.

   The same configuration can be provided via YAML:

   ```yaml
   simulators:
     - simple
     - indel
   constraints:
     max_homopolymer: 5
   ```

```bash
genecli channel run config.yml
```

   The command processes each FASTA record through a pipeline of steps. Set
   ``batch_workers`` in the YAML configuration to run multiple records in
   parallel:

```bash
genecli channel run config.yml
```

15. **Add DNA decay to the channel pipeline**

   Simulate long‑term storage by including a ``decay`` stage. ``half_life``
   controls how quickly bases are lost and ``variation`` adds random jitter to
   the process. The stage randomly removes nucleotides from the sequence so
   lower values or higher variation lead to more dropouts.

   ```yaml
   simulators:
     - simple
   decay:
     half_life: 1000   # days
     variation: 0.1
   ```

```bash
genecli channel run decay_config.yml
```

16. **AI-assisted decoding**

   Install the optional `dnaformer` extras to enable a machine learning model
   that can recover sequences with high error rates:

   ```bash
   poetry install --extras dnaformer --no-interaction
   genecli decode --input-files noisy.fasta --output-file out.bin \
       --method ai
   ```

   Or install the alternative `deepdna` extras:

   ```bash
   poetry install --extras deepdna --no-interaction
   genecli decode --input-files noisy.fasta --output-file out.bin \
       --method ai
   ```

17. **Run the multi-oligo encode → channel → decode flow**

   Multi-oligo runs use streaming encode output, a dropout-aware channel configuration, and a standard decode step. Start by encoding the payload into a `SequenceBatch` with per-oligo metadata:

   ```bash
   genecli encode --input-files examples/pipeline_demo_input.txt \
       --output-file encoded/multi_oligo_stream.fasta --stream --chunk-size 500000
   ```

   Define the channel stage with `dropout_rate` and `coverage_distribution` so coverage variation is tracked in the manifest. The sample lives at `configs/channel_multi_oligo.yaml`:

   ```yaml
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

   Run the channel and decode the surviving strands:

   ```bash
   genecli channel run configs/channel_multi_oligo.yaml
   genecli decode --input-files simulated_multi_oligo.fasta --output-file decoded_multi.txt
   ```

   The resulting `decoded_multi.txt.json` manifest lists dropout counts, coverage histograms, and oligo-level GC and homopolymer metrics. Open it with `genecli dashboard` or a browser pointed at the rebuilt React dashboard. Preview the updated documentation and diagrams locally with `mkdocs serve`.

### MPI Channel Pipeline

`ChannelPipeline` can distribute work across multiple machines using MPI.
Enable this by setting `use_mpi: true` in the pipeline section of your YAML
configuration and running the command with `mpiexec`.

```yaml
pipeline:
  parallel: true
  workers: 4
  use_mpi: true
```

```bash
pip install mpi4py
mpiexec -n 4 genecli channel run pipeline.yml
```

MPI execution requires the `mpi4py` package and an MPI implementation such as
MPICH or OpenMPI.

### MPI Pipeline

The full encode->FEC->channel->decode pipeline can also run under MPI when
`mpi4py` is installed. Set `use_mpi` and the desired number of `workers` in your
YAML configuration or pass `--use-mpi` on the command line.

```yaml
pipeline:
  use_mpi: true
  workers: 4
```

Install the optional dependency and execute with `mpiexec`:

```bash
pip install mpi4py
mpiexec -n 4 genecli pipeline run pipeline.yml --use-mpi
```

### Manifest files

Each encoded file produces a companion JSON manifest capturing the encoding
parameters and basic metrics. The manifest is saved alongside the FASTA output
using the `.manifest.json` extension.

Example snippet:

```json
{
  "file": "example.txt",
  "encoding_parameters": {"method": "base4_direct"},
  "metrics": {"dna_length": 42}
}
```

See [Manifest Format](manifest.md) for the full structure and required keys.

Generate a standalone HTML summary from a manifest:

```bash
genecli html-report --manifest encoded/example.txt.manifest.json \
    --output-file summary.html
```



### Capsule output

Use `--capsule` to store the encoded DNA and related metadata in a single JSON file. The structure includes:

```
{
  "version": 1,
  "header": "<fasta header>",
  "sequence": "<dna sequence>",
  "metadata": {"input_file": "<source file>", "method": "<encoding method>", "fec": "<fec method or null>"},
  "created": "<timestamp>"
}
```

This option works only with one input file. Example:

```bash
genecli encode --input-files msg.txt \
    --output-dir out/ --method base4_direct \
    --capsule seq.capsule
```
### Security Options

Use `--encrypt` to encrypt the input bytes. The `--key <file>` option must
provide the encryption key bytes. The `--checksum` flag stores a SHA256
checksum of the plaintext in the FASTA header which is validated during
decoding.


```bash
genecli encode --input-files secret.txt \
    --output-dir out/ --method base4_direct --encrypt --key key.bin --checksum
genecli decode --input-files out/secret.txt.fasta \
    --output-dir decoded/ --method base4_direct --encrypt --key key.bin --checksum

```

### Offline Operation

GeneCoder functions without network access. Plugins are discovered from packages
already installed in the current Python environment. Remote registries or
catalogs are only consulted when `GENECODER_PLUGIN_REGISTRY_URL` or
`GENECODER_PLUGIN_CATALOG_URL` is set. For air‑gapped deployments leave these
variables unset or set them to empty strings:

```bash
export GENECODER_PLUGIN_REGISTRY_URL=
export GENECODER_PLUGIN_CATALOG_URL=
```

Simulator profiles used by external tools are cached under
`~/.genecoder/data` by default. Set `GENECODER_DATA_DIR` to change this
location. Provide pre-downloaded profiles via `GENECODER_PROFILE_DIR` to
run simulators without network access.

### Validating bundle configurations

Bundle runs are validated against `configs/schema/bundle.schema.json` before
execution. A minimal configuration demonstrating valid `encode`, `simulate` and
`decode` blocks looks like:

```yaml
encode:
  input_files:
    - examples/pipeline_demo_input.txt
  method: base4_direct
  fec: hamming_7_4
simulate:
  simulators:
    - illumina
  pipeline:
    illumina_profile: hiseq
decode:
  method: base4_direct
```

To lint a bundle without running it, load the YAML and apply the schema:

```bash
python - <<'PY'
import json
import yaml
from jsonschema import Draft202012Validator

schema = json.load(open("configs/schema/bundle.schema.json", "r", encoding="utf-8"))
data = yaml.safe_load(open("configs/pipeline_demo.yaml", "r", encoding="utf-8"))
Draft202012Validator(schema).validate(data)
print("bundle config is valid")
PY
```

`genecli bundle run` will emit a clear error if the schema is violated (for
example, due to unknown keys or type mismatches).

## Graphical User Interface (GUI)

### Launching the Flet App

Install the GUI dependencies with the optional `gui` group:

```bash
poetry install --with gui --no-interaction
```

Run the application:

```bash
python -m genecoder.flet_app
```

The GUI exposes encoding options, error correction choices and displays metrics and analysis plots.

## Dashboard

The dashboard visualizes simulation output stored in a JSON file.
Generate a sample set of metrics by running the provided pipeline demo
configuration and then launch the Streamlit interface:

```bash
poetry install --with gui --no-interaction
genecli bundle run configs/pipeline_demo.yaml \
    --metrics-path examples/pipeline_metrics.json \
    --emit-manifest-report \
    --launch-dashboard
```

This encodes and decodes `examples/pipeline_demo_input.txt`, stores metrics in
`examples/pipeline_metrics.json` and opens the dashboard with the results. Drop
`--launch-dashboard` if you prefer to open the file later via
`genecli dashboard examples/pipeline_metrics.json`.

The interface visualizes key metrics:

* GC-content distribution
* Homopolymer run distribution
* ECC success-rate bar charts

Use the **Error Types** multiselect in the sidebar to toggle which histograms
are shown. Each bar chart illustrates how often reads contain a given number of
substitutions, insertions or deletions.

![Homopolymer distribution screenshot](images/homopolymer_distribution.svg)

![Error rate charts screenshot](images/error_rates.svg)

Example metrics snippet:

```json
{
  "substitutions": 12,
  "insertions": 3,
  "deletions": 1,
  "coverage_distribution": [1, 3, 2],
  "constraint_violations": 2
}
```

If you prefer to analyze bundles without running the FastAPI service, export the
aggregated manifest metrics directly from the cache directory:

```bash
genecli stats bundle --runs runs/desp --output runs/desp/bundle_metrics.json
```

The resulting JSON mirrors the `/bundle-metrics` endpoint output and can be
passed to `genecli dashboard` for offline comparison plots.

### Constraint Fix Suggestions

Both the CLI `analyze` command and the GUI provide simple suggestions when a
sequence falls outside the enforced 45–55% GC window or exceeds the default
three-base homopolymer limit. After running `genecli analyze`, a log entry shows
the GC content and maximum homopolymer length of an adjusted sequence. The GUI displays a
"Suggested fix" message beneath the encoding status when applicable.

The **Visualizer** tab embeds a dedicated React/Three.js frontend. It renders the
sequence in 3D with orbit controls, overlays for
[GC content](glossary.md#gc-content) and
[homopolymers](glossary.md#homopolymer). The viewer now includes progress
**pulses**, GC gauges and homopolymer bars along the helix. An *Animate* toggle
and fullscreen button make the visualization interactive. The frontend lives
under `web/helix-ui` and is loaded via a WebView in the GUI.

### Advanced Constraint Fixing

Install the optional `chisel` extras to leverage a more sophisticated
constraint solver:

```bash
poetry install --extras chisel --no-interaction
```

Pass `--fix-chisel` to `genecli encode` or `genecli analyze` to automatically
adjust sequences so they satisfy strict GC and homopolymer limits. The option
uses the ``dnachisel_fixer`` plugin when available:

```bash
genecli encode --input-files sample.bin \
    --output-dir fixed/ --method base4_direct --fix-chisel
```

## Disclaimer

GeneCoder is intended for educational simulations only. It should not be used
to handle personal or medical DNA data. See the
[README's Disclaimer](../README.md#disclaimer) for full details.

#### Default GC/homopolymer guardrails

`genecli encode`, the GUI, and constraint-fixing helpers all validate payloads
against an enforced 45–55% GC range and a maximum homopolymer run of 3 bases.
These checks run even if you do not pass constraint flags. When a sequence falls
outside those guardrails, the CLI logs a warning and the GUI highlights the
violation.

Override the defaults by supplying constraint options explicitly:

```bash
genecli encode input.bin --method gc_balanced \
    --gc-min 0.40 --gc-max 0.60 --max-homopolymer 5
```

YAML configurations and the pipeline runner accept the same keys:

```yaml
constraints:
  gc_min: 0.40
  gc_max: 0.60
  max_homopolymer: 5
```

You can also provide the parameters when calling `genecli analyze`, `genecli
bundle`, or the dashboard pipeline presets. If you simply want to silence the
warnings while keeping the defaults, pass `--suppress-constraint-warnings` to
`genecli encode`.

### Bundle configs and schema validation

Use `genecli bundle run` to connect encoding, simulation and decoding in a single
YAML config. A minimal, schema-compliant configuration looks like:

```yaml
encode:
  input_files:
    - examples/pipeline_demo_input.txt
  method: base4_direct
  fec: hamming_7_4
simulate:
  simulators:
    - illumina
  pipeline:
    illumina_profile: hiseq
decode:
  method: base4_direct
```

The `fec` field is validated against the registered error-correcting codes
(`triple_repeat`, `hamming_7_4`, `reed_solomon`, `ldpc`, `fountain`, `bch`,
`raptorq`, plus any plugins), and simulators must match known adapters such as
`illumina`, `nanopore`, `squigulator`, or `desp`. Run the JSON Schema linter
before executing a bundle to catch typos and type mismatches:

```bash
python -m jsonschema -i configs/pipeline_demo.yaml configs/schema/bundle.schema.json
```

Successful validation means `genecli bundle run` will accept the config without
extra flag parsing errors.
