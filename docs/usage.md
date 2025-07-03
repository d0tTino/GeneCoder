# Usage

## Command-Line Interface (CLI)

See the [Disclaimer](../README.md#disclaimer) before using the toolkit.

For a hands-on introduction check the Jupyter notebooks in the [notebooks/](../notebooks) directory.

GeneCoder operations are performed with the `genecoder` CLI:

```bash
genecoder <command> --input-files <path1> [<path2> ...] \
    [--output-file <path>] [--output-dir <dir>] \
    --method <method_name> [--fec <fec_method>] [options]
```

Run `genecoder --help` to see all available commands:

```bash
genecoder --help
```

Example output:

A quick sanity check is to run the command and ensure the usage header appears.

```bash
$ genecoder --help | head -n 5
Usage: genecoder [-h] [--version] {encode,decode,analyze,simulate-errors} ...
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
   genecoder encode --input-files path/to/your_document.txt \
       --output-file encoded_base4.fasta --method base4_direct
   ```

2. **Decode using Base-4 Direct Mapping**

   ```bash
   genecoder decode --input-files path/to/encoded_base4.fasta \
       --output-file decoded_document.txt --method base4_direct
   ```

3. **Encode with Huffman, parity and Triple-Repeat FEC**

   ```bash
   genecoder encode --input-files path/to/my_data.bin \
       --output-dir encoded_output/ --method huffman \
       --add-parity --fec triple_repeat
   ```

4. **Encode using the base6 alphabet**

   ```bash
   genecoder encode --input-files data.bin \
       --output-file encoded_base6.fasta --alphabet base6
   ```

   Base5 and base6 are convenience alphabets that map the 2-bit output of
   `base4_direct` to different nucleotide symbols. They do **not** store more
   information per base.

5. **Encode with Base-4 Direct and Hamming(7,4) FEC**

   ```bash
   genecoder encode --input-files path/to/important_data.txt \
       --output-dir encoded_hamming/ --method base4_direct --fec hamming_7_4
   ```

6. **Decode a Hamming(7,4) encoded file**

   ```bash
   genecoder decode --input-files encoded_hamming/important_data.txt.fasta \
       --output-file decoded_important_data.txt --method base4_direct
   ```

7. **Batch encode multiple files using GC-Balanced**

   ```bash
   genecoder encode --input-files file1.txt notes.md image.png \
       --output-dir gc_encoded_batch/ --method gc_balanced \
       --gc-min 0.40 --gc-max 0.60 --max-homopolymer 4
   ```

8. **Batch decode multiple FASTA files**

   ```bash
   genecoder decode --input-files gc_encoded_batch/*.fasta \
       --output-dir decoded_batch/ --method gc_balanced
   ```

9. **Stream encode and decode a large file**

   ```bash
   genecoder encode --input-files big.bin --output-file big.fasta \
       --stream --method base4_direct
   genecoder decode --input-files big.fasta --output-file big_decoded.bin \
       --stream --method base4_direct
   ```

   Streaming operations are **resumable**. Pass `--resume state.json` to
   continue an interrupted encode or decode run.

10. **Decode with simulated channel errors**

   ```bash
   genecoder decode --input-files encoded.fasta \
       --output-file decoded.bin --simulate-errors 0.02
   ```

   Set the environment variable `GENECODER_SIM_SEED` to an integer to make the
   simulated substitutions deterministic across runs.

11. **Encode, corrupt and decode a file with automatic extensions**

   ```bash
   genecoder encode --input-files hello.jpg --output-dir encoded \
       --method base4_direct --auto-ext
   genecoder simulate-errors encoded/hello.jpg.dna --sub-rate 0.01 \
       --output-file corrupted.dna
   genecoder decode corrupted.dna --output-dir decoded --auto-ext
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
   genecoder decode --input-files encoded.fasta \
       --output-file decoded.bin --simulator squigulator
   ```

13. **Combine simulators into a channel**

   Apply multiple simulators and enforce synthesis constraints:

   ```bash
   genecoder channel --input-file encoded.fasta \
       --output-file channel.fasta --simulator simple --simulator indel
   ```

   The same configuration can be provided via YAML:

   ```yaml
   simulators:
     - simple
     - indel
   constraints:
     max_homopolymer: 5
   ```

   ```bash
   genecoder channel --input-file encoded.fasta \
       --output-file channel.fasta --config config.yml
   ```

14. **AI-assisted decoding**

   Install the optional `dnaformer` extras to enable a machine learning model
   that can recover sequences with high error rates:

   ```bash
   poetry install --extras dnaformer --no-interaction
   genecoder decode --input-files noisy.fasta --output-file out.bin \
       --method ai
   ```

   Or install the alternative `deepdna` extras:

   ```bash
   poetry install --extras deepdna --no-interaction
   genecoder decode --input-files noisy.fasta --output-file out.bin \
       --method ai
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
genecoder encode --input-files msg.txt \
    --output-dir out/ --method base4_direct \
    --capsule seq.capsule
```
### Security Options

Use `--encrypt` to XOR-encrypt the input bytes. You **must** provide your own
key via `--key <file>` as GeneCoder does not include a secure default. The
`--checksum` flag stores a SHA256 checksum of the plaintext in the FASTA header
which is validated during decoding.

```bash
genecoder encode --input-files secret.txt \
    --output-dir out/ --method base4_direct --encrypt --key key.bin --checksum
genecoder decode --input-files out/secret.txt.fasta \
    --output-dir decoded/ --method base4_direct --encrypt --key key.bin --checksum

```
## Graphical User Interface (GUI)

### Launching the Flet App

Install the optional GUI extras:

```bash
poetry install --with gui --no-interaction
```

Run the application:

```bash
python -m genecoder.flet_app
```

The GUI exposes encoding options, error correction choices and displays metrics and analysis plots.

### Constraint Fix Suggestions

Both the CLI `analyze` command and the GUI provide simple suggestions when a
sequence falls outside the 40-60% GC range or exceeds the default homopolymer
limit. After running `genecoder analyze`, a log entry shows the GC content and
maximum homopolymer length of an adjusted sequence. The GUI displays a
"Suggested fix" message beneath the encoding status when applicable.

The **Visualizer** tab embeds a dedicated React/Three.js frontend. It renders the
sequence in 3D with orbit controls, overlays for
[GC content](glossary.md#gc-content) and
[homopolymers](glossary.md#homopolymer). The viewer now includes progress
**pulses**, GC gauges and homopolymer bars along the helix. An *Animate* toggle
and fullscreen button make the visualization interactive. The frontend lives
under `web/helix-ui` and is loaded via a WebView in the GUI.

## Disclaimer

GeneCoder is intended for educational simulations only. It should not be used
to handle personal or medical DNA data. See the
[README's Disclaimer](../README.md#disclaimer) for full details.

