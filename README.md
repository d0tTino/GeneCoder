# GeneCoder: Simulated DNA Data Encoding & Exploration

**An open, educational software toolkit for simulating DNA data encoding and decoding, bringing the concepts of molecular data storage to your fingertips.**

---

## Current Status: MVP Functionality Achieved! 🎉

**GeneCoder's Minimum Viable Product (MVP) is now functional!** (As of latest update)

The core command-line interface for encoding and decoding data using initial schemes is implemented. You can now experiment with converting files into simulated DNA and back.

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
    *   **Base-4 Direct Mapping:**
        *   A straightforward scheme where each byte of input data is converted into four DNA nucleotides.
        *   Each 2-bit pair from the input byte (processed Most Significant Bit first) maps directly to a nucleotide:
            *   `00` -> `A`
            *   `01` -> `T`
            *   `10` -> `C`
            *   `11` -> `G`
    *   **Huffman-4 Coding:**
        *   An adaptive encoding method that first calculates byte frequencies in the input data.
        *   Builds a Huffman tree to generate variable-length binary codes for each input byte (more frequent bytes get shorter codes).
        *   These binary codes are concatenated, padded with '0's if necessary to ensure an even length, and then mapped to DNA using the same 2-bit to nucleotide mapping as Base-4 Direct.
*   **Decoding Engine:**
    *   Reliable decoding for both `base4_direct` and `huffman` methods.
    *   Error detection for invalid DNA characters during decoding.
*   **Output Format:**
    *   **Encoded Data:** Output is in FASTA format (`.fasta`).
        *   The FASTA header line includes metadata: encoding method used and the original input file name.
        *   For the `huffman` method, the header also contains a JSON string with the specific Huffman table (mapping original byte values to binary codes) and the number of padding bits used. This information is crucial for correct decoding.
    *   **Decoded Data:** The output is the original binary file.
*   **Encoding Metrics Display:**
    *   When encoding, the CLI displays:
        *   Original file size (bytes).
        *   Encoded DNA length (nucleotides).
        *   Compression ratio (original bytes / DNA bytes equivalent, where 1 nucleotide = 2 bits = 0.25 bytes).
        *   Achieved bits per nucleotide (total bits in original data / number of nucleotides in encoded sequence).

---

## Usage

To use GeneCoder, navigate to the project's root directory in your terminal. The main script is `src/cli.py`.

**General Command Structure:**
`python src/cli.py <command> --input-file <input_path> --output-file <output_path> --method <method_name>`

**Examples:**

1.  **Encode using Base-4 Direct Mapping:**
    ```bash
    python src/cli.py encode --input-file path/to/your_document.txt --output-file path/to/encoded_base4.fasta --method base4_direct
    ```

2.  **Decode using Base-4 Direct Mapping:**
    ```bash
    python src/cli.py decode --input-file path/to/encoded_base4.fasta --output-file path/to/decoded_document.txt --method base4_direct
    ```

3.  **Encode using Huffman-4 Coding:**
    ```bash
    python src/cli.py encode --input-file path/to/your_image.png --output-file path/to/encoded_huffman.fasta --method huffman
    ```
    *Output for this command will include encoding metrics printed to the console. The `encoded_huffman.fasta` file will have a header containing the Huffman table and padding information required for decoding.*

4.  **Decode using Huffman-4 Coding:**
    ```bash
    python src/cli.py decode --input-file path/to/encoded_huffman.fasta --output-file path/to/decoded_image.png --method huffman
    ```
    *This command relies on the Huffman parameters stored in the FASTA header of `encoded_huffman.fasta`.*

---

## Technology Stack (Used for MVP)

*   **Language:** Python (≥ 3.10 recommended)
*   **Core Libraries (Python Standard Library):**
    *   `argparse` (for CLI argument parsing)
    *   `json` (for serializing Huffman table in FASTA headers)
    *   `collections.Counter` (for frequency analysis in Huffman coding)
    *   `heapq` (for building Huffman trees)
    *   `pathlib` (implicitly used for path handling, though not explicitly imported in current code)

---

## Development Roadmap (High-Level)

1.  **MVP - Foundation Implemented:**
    *   CLI-based encoding and decoding.
    *   Encoding methods: Base-4 Direct Mapping and Huffman-4 Coding.
    *   FASTA formatted output with metadata (including Huffman parameters).
    *   Display of encoding metrics (original size, DNA length, compression ratio, bits/nt).
    *   Robust FASTA parsing for decoding.
    *   Comprehensive unit tests for core logic.
2.  **Phase 2 (Future):** Introduce basic error-resilience simulation (e.g., simple parity checks or triple modular redundancy concepts), develop a simple GUI (potentially using a lightweight framework like Tkinter or Flet), and add plotting for metrics comparison.
3.  **Phase 3 & Beyond (Future):** Explore more advanced concepts like GC-content balancing in encoding, simplified error correction codes (e.g., Hamming codes), support for larger files through streaming/batch processing, and potentially a plug-in API for users to experiment with their own encoding schemes.

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
