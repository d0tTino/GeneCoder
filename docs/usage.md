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
* `--fec` – optional FEC method (`triple_repeat`, `hamming_7_4`, `reed_solomon`).

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

4. **Encode with Base-4 Direct and Hamming(7,4) FEC**

   ```bash
   genecoder encode --input-files path/to/important_data.txt \
       --output-dir encoded_hamming/ --method base4_direct --fec hamming_7_4
   ```

5. **Decode a Hamming(7,4) encoded file**

   ```bash
   genecoder decode --input-files encoded_hamming/important_data.txt.fasta \
       --output-file decoded_important_data.txt --method base4_direct
   ```

6. **Batch encode multiple files using GC-Balanced**

   ```bash
   genecoder encode --input-files file1.txt notes.md image.png \
       --output-dir gc_encoded_batch/ --method gc_balanced \
       --gc-min 0.40 --gc-max 0.60 --max-homopolymer 4
   ```

7. **Batch decode multiple FASTA files**

   ```bash
   genecoder decode --input-files gc_encoded_batch/*.fasta \
       --output-dir decoded_batch/ --method gc_balanced
   ```

8. **Stream encode and decode a large file**

   ```bash
   genecoder encode --input-files big.bin --output-file big.fasta \
       --stream --method base4_direct
   genecoder decode --input-files big.fasta --output-file big_decoded.bin \
       --stream --method base4_direct
   ```

9. **Decode with simulated channel errors**

   ```bash
   genecoder decode --input-files encoded.fasta \
       --output-file decoded.bin --simulate-errors 0.02
   ```

## Graphical User Interface (GUI)

Launch the Flet application:

```bash
python src/genecoder/flet_app.py
```

The GUI exposes encoding options, error correction choices and displays metrics and analysis plots.
