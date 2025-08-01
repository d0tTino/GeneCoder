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

Run `genecli --help` to see all available commands:

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
* `--auto-ext` – save encoded files with a `.dna` suffix and decode back to the original extension.

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

6. **Decode a Hamming(7,4) encoded file**

   ```bash
   genecli decode --input-files encoded_hamming/important_data.txt.fasta \
       --output-file decoded_important_data.txt --method base4_direct
   ```

7. **Batch encode multiple files using GC-Balanced**

   ```bash
   genecli encode --input-files file1.txt notes.md image.png \
       --output-dir gc_encoded_batch/ --method gc_balanced \
       --gc-min 0.40 --gc-max 0.60 --max-homopolymer 4
   ```

8. **Batch decode multiple FASTA files**

   ```bash
   genecli decode --input-files gc_encoded_batch/*.fasta \
       --output-dir decoded_batch/ --method gc_balanced
   ```

9. **Stream encode and decode a large file**

   ```bash
   genecli encode --input-files big.bin --output-file big.fasta \
       --stream --method base4_direct
   genecli decode --input-files big.fasta --output-file big_decoded.bin \
       --stream --method base4_direct
   ```

   Streaming operations are **resumable**. Pass `--resume state.json` to
   continue an interrupted encode or decode run.

10. **Introduce channel errors before decoding**

   ```bash
   genecli channel --input-file encoded.fasta --output-file corrupted.fasta \
       --sub-prob 0.02
   genecli decode corrupted.fasta --output-file decoded.bin
   ```

   Set the environment variable `GENECODER_SIM_SEED` to an integer to make the
   simulated substitutions deterministic across runs.

11. **Encode, corrupt and decode a file with automatic extensions**

   ```bash
   genecli encode --input-files hello.jpg --output-dir encoded \
       --method base4_direct --auto-ext
   genecli channel --input-file encoded/hello.jpg.dna --output-file corrupted.dna \
       --sub-prob 0.01
   genecli decode corrupted.dna --output-dir decoded --auto-ext
   ```

   Verify the round-trip checksum:

   ```bash
   sha256sum hello.jpg decoded/hello.jpg
   ```

   Add `--checksum` to the encode and decode commands for automatic validation.
12. **Decode using an external simulator**

   The ``--simulator`` option accepts ``d2sim``, ``dnarsim`` or ``squigulator``.
   Install the desired simulator separately and ensure the command is on your
   ``PATH``:

   * ``d2sim`` — [D2Sim](https://github.com/kurimsw/d2sim). Follow the
     instructions in the repository to build the binary and place ``d2sim`` on
     your ``PATH``.
   * ``dnarsim`` — [DNArSim](https://github.com/Purdue-ScottLab/DNArSim)
   * ``squigulator`` — [Squigulator](https://github.com/hasindu2008/squigulator)

   The ``d2sim`` adapter is bundled with GeneCoder and is registered
   automatically. Once the ``d2sim`` command is available you can invoke it with
   ``--simulator d2sim``.

   When a command is missing GeneCoder automatically falls back to an internal
   error model.

   The same simulators can be accessed programmatically via
   ``genecoder.simulators.simulate_reads``.

   ```bash
   genecli decode --input-files encoded.fasta \
       --output-file decoded.bin --simulator squigulator
   ```

13. **Combine simulators into a channel**

   Apply multiple simulators and enforce synthesis constraints:

   ```bash
   genecli channel --input-file encoded.fasta \
       --output-file channel.fasta --simulator simple --simulator indel
   ```

   Named sequencing profiles are available:

   - **Illumina** – `miseq`, `hiseq`
   - **Nanopore** – `minion`, `promethion`

   Select a profile with `--illumina-profile` or `--nanopore-profile`. Individual rate options
   override the chosen profile.

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

14. **Add DNA decay to the channel pipeline**

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

15. **AI-assisted decoding**

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

16. **Run the full pipeline from a YAML file**

   Create a configuration with the codec, FEC and channel settings:

   ```yaml
   codec: base4_direct
   fec: reed_solomon
   channel:
     name: simple
     substitution_rate: 0.01
   ```

   Then execute:

  ```bash
  genecli pipeline input.bin output.bin --config pipeline.yml
  ```

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

### Launching the Streamlit Dashboard

The dashboard visualizes simulation output stored in a JSON file. Install the `gui` group and run:

```bash
poetry install --with gui --no-interaction
genecli dashboard results.json
```

The interface plots GC content distribution, homopolymer histograms, and ECC success-rate bar charts. It also displays the overall decode success percentage derived from the metrics file. When substitution, insertion and deletion counts are present, they are shown as a simple bar chart.

Example metrics snippet:

```json
{
  "substitutions": 12,
  "insertions": 3,
  "deletions": 1
}
```

### Constraint Fix Suggestions

Both the CLI `analyze` command and the GUI provide simple suggestions when a
sequence falls outside the 40-60% GC range or exceeds the default homopolymer
limit. After running `genecli analyze`, a log entry shows the GC content and
maximum homopolymer length of an adjusted sequence. The GUI displays a
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

