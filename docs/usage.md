# Usage

## Command-Line Interface (CLI)

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

If the `genecoder` command isn't found, install the project in editable mode:

```bash
pip install -e .
```

* `--input-files` – one or more input files.
* `--output-file` – output path for a single input file.
* `--output-dir` – directory for batch operations.
* `--fec` – optional FEC method (`triple_repeat`, `hamming_7_4`, `reed_solomon`, `ldpc`, `fountain`).

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

10. **Decode with simulated channel errors**

   ```bash
   genecoder decode --input-files encoded.fasta \
       --output-file decoded.bin --simulate-errors 0.02
   ```

11. **Decode using an external simulator**

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


   ```bash
   genecoder decode --input-files encoded.fasta \
       --output-file decoded.bin --simulator squigulator
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
## Graphical User Interface (GUI)

### Launching the Flet App

Install the optional GUI extras:

```bash
pip install .[gui]  # or pip install -e .[gui] for development
```

Run the application:

```bash
python -m genecoder.flet_app
```

The GUI exposes encoding options, error correction choices and displays metrics and analysis plots.

The **Helix View** tab now features an animated 3D helix complete with nucleotide
tooltips and simple overlays illustrating GC content and homopolymer regions.
Toggle the *Animate* checkbox or adjust the *Zoom* slider to explore the visualization.
