# Usage

## Command-Line Interface (CLI)

GeneCoder operations are performed with `src/cli.py`:

```bash
python src/cli.py <command> --input-files <path1> [<path2> ...] \
    [--output-file <path>] [--output-dir <dir>] \
    --method <method_name> [--fec <fec_method>] [options]
```

* `--input-files` – one or more input files.
* `--output-file` – output path for a single input file.
* `--output-dir` – directory for batch operations.
* `--fec` – optional FEC method (`triple_repeat`, `hamming_7_4`, `reed_solomon`).

See [WORKFLOWS.md](../WORKFLOWS.md) for a step-by-step overview.

### Examples

1. **Encode using Base-4 Direct Mapping**

   ```bash
   python src/cli.py encode --input-files path/to/your_document.txt \
       --output-file encoded_base4.fasta --method base4_direct
   ```

2. **Decode using Base-4 Direct Mapping**

   ```bash
   python src/cli.py decode --input-files path/to/encoded_base4.fasta \
       --output-file decoded_document.txt --method base4_direct
   ```

3. **Encode with Huffman, parity and Triple-Repeat FEC**

   ```bash
   python src/cli.py encode --input-files path/to/my_data.bin \
       --output-dir encoded_output/ --method huffman \
       --add-parity --fec triple_repeat
   ```

4. **Encode with Base-4 Direct and Hamming(7,4) FEC**

   ```bash
   python src/cli.py encode --input-files path/to/important_data.txt \
       --output-dir encoded_hamming/ --method base4_direct --fec hamming_7_4
   ```

5. **Decode a Hamming(7,4) encoded file**

   ```bash
   python src/cli.py decode --input-files encoded_hamming/important_data.txt.fasta \
       --output-file decoded_important_data.txt --method base4_direct
   ```

6. **Batch encode multiple files using GC-Balanced**

   ```bash
   python src/cli.py encode --input-files file1.txt notes.md image.png \
       --output-dir gc_encoded_batch/ --method gc_balanced \
       --gc-min 0.40 --gc-max 0.60 --max-homopolymer 4
   ```

7. **Batch decode multiple FASTA files**

   ```bash
   python src/cli.py decode --input-files gc_encoded_batch/*.fasta \
       --output-dir decoded_batch/ --method gc_balanced
   ```

8. **Stream encode and decode a large file**

   ```bash
   python src/cli.py encode --input-files big.bin --output-file big.fasta \
       --stream --method base4_direct
   python src/cli.py decode --input-files big.fasta --output-file big_decoded.bin \
       --stream --method base4_direct
   ```

9. **Decode with simulated channel errors**

   ```bash
   python src/cli.py decode --input-files encoded.fasta \
       --output-file decoded.bin --simulate-errors 0.02
   ```

## Graphical User Interface (GUI)

Launch the Flet application:

```bash
python src/flet_app.py
```

The GUI exposes encoding options, error correction choices and displays metrics and analysis plots.
