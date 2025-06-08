# GeneCoder: Simulated DNA Data Encoding & Exploration

[![Codecov Coverage](https://codecov.io/gh/d0tTino/GeneCoder/branch/main/graph/badge.svg)](https://codecov.io/gh/d0tTino/GeneCoder)

**An open, educational software toolkit for simulating DNA data encoding and decoding, bringing the concepts of molecular data storage to your fingertips.**

*The badge above reports the current coverage of GeneCoder's unit tests.*

The coverage report intentionally **excludes** `src/flet_app.py` (the GUI entry
point) via the `.coveragerc` configuration. Codecov picks up this setting when
processing `coverage.xml`.

---

## Current Status: Evolving with New Features! 🚀

**GeneCoder has been enhanced with new encoding strategies, error correction, batch processing, and an improved GUI!** (As of latest update)

The toolkit now offers more sophisticated ways to simulate DNA data storage, including GC-content balancing, triple-repeat error correction, and the ability to process multiple files efficiently. The Flet-based GUI has also been updated for better responsiveness and to include these new options.

---

## Vision & Core Concept

GeneCoder aims to demystify the fascinating world of DNA-based data storage. Our goal is to provide an accessible, hands-on tool that allows users to:

* **Encode** arbitrary text or binary files into simulated DNA sequences (A, T, C, G).
* **Decode** these sequences back into their original data form.
* **Explore** different encoding strategies and understand their trade-offs.
* **Learn** about fundamental concepts like data compression, channel coding, bioinformatics file formats (like FASTA), and the error-prone nature of molecular data – all without needing a wet lab!

**Why does this matter?** DNA boasts theoretical storage densities orders of magnitude greater than current magnetic or silicon-based media (potentially ~1 exabyte per gram!). By simulating the encoding/decoding pipeline, GeneCoder will help learners and enthusiasts grasp both the incredible promise and the inherent challenges of this revolutionary technology.

---

## Implemented MVP Features

The current version of GeneCoder, built around a Command-Line Interface (CLI), delivers the following core functionalities:

*   **CLI for Encoding & Decoding:** A user-friendly CLI (`src/cli.py`) to perform encoding and decoding operations.
*   **Input Handling:**
    *   Accepts arbitrary binary files as input for encoding (UTF-8 text files are also handled as binary).
*   **Encoding Methods:**
    *   **Base-4 Direct Mapping:** (As described before)
    *   **Huffman-4 Coding:** (As described before)
    *   **GC-Balanced Encoder (`gc_balanced`):**
        *   Aims to produce DNA sequences within a target GC content range and with a maximum homopolymer run length.
        *   These constraints can be tuned via `--gc-min`, `--gc-max`, and `--max-homopolymer` (defaults: `0.45`, `0.55`, `3`).
        *   It first attempts to encode data directly (using Base-4 Direct). If constraints are met, the sequence is prefixed with '0'.
        *   If constraints are violated, the input data bits are inverted, re-encoded, and the sequence is prefixed with '1'. This provides an alternative sequence that might meet constraints.
        *   The FASTA header includes `method=gc_balanced`, `gc_min`, `gc_max`, and `max_homopolymer` (target constraint values).
        *   Metrics reported include actual GC content and actual maximum homopolymer length of the payload.
*   **Forward Error Correction (FEC):**
    *   **Triple-Repeat FEC (`--fec triple_repeat`):**
        *   Encodes the output of any primary encoding method by repeating each nucleotide three times (e.g., "ATGC" becomes "AAATTTGGGCC").
        *   During decoding, it uses a majority vote on each triplet to correct single errors within that triplet.
        *   If FEC was used, the FASTA header will include `fec=triple_repeat`.
        *   The decoder reports the number of corrected and uncorrectable errors found in triplets.
    *   **Hamming(7,4) FEC (`--fec hamming_7_4`):**
        *   A block code that processes 4 bits of binary data into 7-bit codewords, capable of correcting single-bit errors within each 7-bit block.
        *   This FEC is applied to the *binary data* before it is converted into a DNA sequence.
        *   The FASTA header will include `fec=hamming_7_4` and `fec_padding_bits=<number>`, where `fec_padding_bits` indicates the number of zero-bits added to the end of the Hamming-encoded bitstream to make its total length a multiple of 8 before byte packing.
        *   The decoder uses these header fields to correctly apply Hamming decoding to the binary data (after DNA decoding) and reports the total number of corrected errors.
        *   Note: If Hamming(7,4) FEC is selected, DNA-level parity (`--add-parity`) is currently ignored as Hamming provides stronger error correction at the binary level.
    *   **Reed-Solomon FEC (`--fec reed_solomon`):**
        *   Adds Reed-Solomon parity bytes to the binary data before DNA encoding.
        *   Requires the optional `reedsolo` library (`pip install reedsolo`).
        *   The FASTA header will include `fec=reed_solomon` and `fec_nsym=<number>` indicating the number of parity symbols used.
        *   During decoding, the same number of symbols is read from the header to repair burst errors. The decoder reports how many symbols were corrected.
*   **Error Detection (Parity):**
    *   Optional parity bit addition for `base4_direct` and `huffman` methods using `--add-parity` (details on rules like `GC_even_A_odd_T` can be found in `error_detection.py`). Parity info is stored in the FASTA header. This is typically used if Hamming(7,4) FEC is not active.
*   **Decoding Engine:**
    *   Reliable decoding for all supported methods and FEC combinations.
    *   Error detection for invalid DNA characters.
*   **Output Format:**
    *   **Encoded Data:** Output is in FASTA format (`.fasta`).
        *   The FASTA header line includes metadata: encoding method, original input file name, and any relevant parameters (Huffman table, GC constraints, parity info, FEC method).
    *   **Decoded Data:** The output is the original binary file.
*   **Encoding Metrics Display (CLI):**
    *   Original file size (bytes).
    *   Final Encoded DNA length (nucleotides, after any FEC).
    *   Compression ratio (original bytes / final DNA bytes equivalent).
    *   Achieved bits per nucleotide (based on final DNA length).
    *   For `gc_balanced`: Actual GC content and max homopolymer length of the payload (pre-FEC).
*   **Graphical User Interface (GUI):**
    *   A Flet-based GUI (`src/flet_app.py`) provides an interactive way to use most encoding/decoding features.
*   Includes options for GC-Balanced encoding, Triple-Repeat FEC, Hamming(7,4) FEC, and Reed-Solomon FEC.
    *   GUI operations are now asynchronous for improved responsiveness.
    *   Displays encoding metrics and analysis plots:
        *   Huffman codeword lengths histogram.
        *   Nucleotide frequency distribution.
        *   Sequence GC & Homopolymer Analysis: Visualizes GC content distribution across the sequence (using a sliding window) and highlights significant homopolymer regions.

---

## Installation

Clone the repository and install the required packages:

```bash
pip install -r requirements.txt
# For exact versions used in CI, see requirements.lock
```


## Usage

### Command-Line Interface (CLI)

To use GeneCoder CLI, navigate to the project's root directory. The main script is `src/cli.py`.
See [WORKFLOWS.md](WORKFLOWS.md) for a step-by-step overview of the encoding and decoding process.

**General Command Structure (Batch and Single File):**
`python src/cli.py <command> --input-files <path1> [<path2> ...] [--output-file <path>] [--output-dir <dir>] --method <method_name> [--fec <fec_method>] [options]`

*   `--input-files`: One or more input files.
*   `--output-file`: Specify for a single input file if not using `--output-dir`.
*   `--output-dir`: Specify for multiple input files, or for a single input if `--output-file` is not used. Output files are named based on input filenames.
*   `--fec`: Optional Forward Error Correction method (`triple_repeat` or `hamming_7_4`). Omit this flag (or pass `--fec None`) to disable FEC.

**CLI Examples:**

1.  **Encode using Base-4 Direct Mapping (single file):**
    ```bash
    python src/cli.py encode --input-files path/to/your_document.txt --output-file path/to/encoded_base4.fasta --method base4_direct
    ```

2.  **Decode using Base-4 Direct Mapping (single file):**
    ```bash
    python src/cli.py decode --input-files path/to/encoded_base4.fasta --output-file path/to/decoded_document.txt --method base4_direct
    ```

3.  **Encode with Huffman, Parity, and Triple-Repeat FEC (single file to output directory):**
    ```bash
    python src/cli.py encode --input-files path/to/my_data.bin --output-dir encoded_output/ --method huffman --add-parity --fec triple_repeat
    ```
    *Metrics and FEC application details will be printed. FASTA header will include Huffman params, parity info, and `fec=triple_repeat`.*

4.  **Encode with Base-4 Direct and Hamming(7,4) FEC:**
    ```bash
    python src/cli.py encode --input-files path/to/important_data.txt --output-dir encoded_hamming/ --method base4_direct --fec hamming_7_4
    ```
    *The FASTA header will include `fec=hamming_7_4` and `fec_padding_bits`. DNA-level parity (`--add-parity`) would be ignored in this case.*

5.  **Decode a file encoded with Base-4 Direct and Hamming(7,4) FEC:**
    ```bash
    python src/cli.py decode --input-files encoded_hamming/important_data.txt.fasta --output-file decoded_important_data.txt --method base4_direct
    ```
    *The decoder reads `fec=hamming_7_4` and `fec_padding_bits` from the header to correctly decode the binary data after DNA decoding. Corrected error counts will be printed.*

6.  **Batch encode multiple files using GC-Balanced method to a specified directory:**
    ```bash
    python src/cli.py encode --input-files file1.txt notes.md image.png \
        --output-dir gc_encoded_batch/ --method gc_balanced \
        --gc-min 0.40 --gc-max 0.60 --max-homopolymer 4
    ```
    *Output: `gc_encoded_batch/file1.txt.fasta`, `gc_encoded_batch/notes.md.fasta`, etc.*

7.  **Batch decode multiple FASTA files from a directory:**
    ```bash
    python src/cli.py decode --input-files gc_encoded_batch/*.fasta --output-dir decoded_batch/ --method gc_balanced
    ```
    *Output: `decoded_batch/file1_decoded.bin`, `decoded_batch/notes_decoded.bin`, etc. (assuming original input names were file1.txt, notes.md)*

8.  **Stream encode and decode a large file:**
    ```bash
    python src/cli.py encode --input-files big.bin --output-file big.fasta --stream --method base4_direct
    python src/cli.py decode --input-files big.fasta --output-file big_decoded.bin --stream --method base4_direct
    ```
    *Processes the file in chunks to avoid high memory usage (currently only for base4_direct without FEC).* 


### Graphical User Interface (GUI)

Run the Flet application:
```bash
python src/flet_app.py
```
The GUI provides controls for most encoding methods and parity. Forward error correction is selectable from a dropdown offering `None`, `Triple-Repeat`, `Hamming(7,4)`, or `Reed-Solomon`. Metric displays and analysis plots are included. GUI operations are asynchronous to keep the interface responsive. See [WORKFLOWS.md](WORKFLOWS.md) for the underlying processing steps.

---

## Technology Stack

*   **Language:** Python 3.10 or 3.11 (tested)
*   **Core Libraries (Python Standard Library):**
    *   `argparse` (for CLI argument parsing)
    *   `json` (for serializing Huffman table in FASTA headers)
    *   `collections.Counter` (for frequency analysis in Huffman coding)
    *   `heapq` (for building Huffman trees)
    *   `concurrent.futures` (for CLI batch processing)
*   **GUI Framework:**
    *   `Flet` (for the cross-platform graphical user interface)
*   **Plotting (for GUI Analysis Tab):**
    *   `Matplotlib` (used to generate plots, then displayed in Flet)

---

## Development Roadmap (High-Level)

1.  **Foundation & Enhancements (Implemented):**
    *   CLI-based encoding and decoding.
    *   Encoding methods: Base-4 Direct, Huffman-4, GC-Balanced.
    *   Error handling: Parity checks, Triple-Repeat FEC (on DNA), Hamming(7,4) FEC, Reed-Solomon FEC (both on binary).
    *   FASTA output with comprehensive metadata.
    *   Display of encoding metrics.
    *   Batch processing for CLI.
    *   Flet-based GUI with asynchronous operations and new feature support.
    *   Comprehensive unit tests.
2.  **Phase 2 (Future):** Explore more advanced error correction codes (e.g., simplified Hamming codes), advanced GC balancing strategies, support for larger files through streaming, and potentially a plug-in API for custom encoding schemes.
3.  **Phase 3 & Beyond (Future):** Deeper simulation of DNA synthesis/sequencing errors, integration with bioinformatics tools, and expanded educational modules.

---

## Contributing

GeneCoder is an open-source educational project. Contributions are welcome! Now that the foundational MVP is in place, there are many avenues for improvement and expansion.

Feel free to:
*   Tackle an existing issue (look for `good first issue` or `help wanted` tags in the future).
*   Propose new features or improvements by opening an issue.
*   Submit pull requests for bug fixes or enhancements.

(Detailed contribution guidelines will be added as the project matures).

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

Happy Forging (or rather, Happy Coding)! We're excited to see how GeneCoder evolves with community input.
