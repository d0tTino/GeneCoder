# GeneCoder: Simulated DNA Data Encoding & Exploration

**An open, educational software toolkit for simulating DNA data encoding and decoding, bringing the concepts of molecular data storage to your fingertips.**

---

## Current Status: Genesis Stage! 🌱

**GeneCoder is a brand new project, freshly conceived and initialized!** (As of May 20, 2025)

The code is not yet written, but the blueprint is ready. This repository will soon house the source code and documentation as development kicks off. Stay tuned!

---

## Vision & Core Concept

GeneCoder aims to demystify the fascinating world of DNA-based data storage. Our goal is to provide an accessible, hands-on tool that allows users to:

* **Encode** arbitrary text or binary files into simulated DNA sequences (A, T, C, G).
* **Decode** these sequences back into their original data form.
* **Explore** different encoding strategies and understand their trade-offs.
* **Learn** about fundamental concepts like data compression, channel coding, bioinformatics file formats (like FASTA), and the error-prone nature of molecular data – all without needing a wet lab!

**Why does this matter?** DNA boasts theoretical storage densities orders of magnitude greater than current magnetic or silicon-based media (potentially ~1 exabyte per gram!). By simulating the encoding/decoding pipeline, GeneCoder will help learners and enthusiasts grasp both the incredible promise and the inherent challenges of this revolutionary technology.

---

## Planned Features (Starting with an MVP)

The initial development phase (MVP - Minimum Viable Product) will focus on delivering core functionality via a Command-Line Interface (CLI):

* **Input Handling:**
    * Accept text (UTF-8) and small binary files (e.g., ≤ 5MB for MVP).
    * Basic file type detection and summary.
* **Encoding Engine (Phase 1 Schemes):**
    * **Base-4 Direct Mapping:** A straightforward 2-bits-per-nucleotide scheme.
    * **Huffman-4 Coding:** An optimized scheme mapping input symbols to variable-length DNA codons, illustrating compression principles.
* **Decoding Engine:**
    * Reliable decoding of the implemented schemes.
    * Error detection for invalid DNA characters.
* **Output:**
    * Raw DNA sequence string.
    * Export to FASTA file format, including metadata in the header.
* **Basic Analysis & Metrics:**
    * Calculation of compression ratio.
    * Achieved bits per nucleotide.

---

## Technology Stack (Planned)

* **Language:** Python (≥ 3.10)
* **Core Libraries (anticipated):** `heapq` (for Huffman trees), `bitarray`, `pathlib`, `argparse`/`click`.
* **Optional (for later enhancements):** `numpy`, `matplotlib` (for visualizations), `rich` (for CLI).

---

## Development Roadmap (High-Level)

1.  **MVP (Weeks 1-2 of development):** CLI-based encoding/decoding with Base-4 and Huffman-4 schemes, FASTA output, and basic metrics.
2.  **Phase 2:** Introduce basic error-resilience simulation (e.g., parity checks), develop a simple GUI (potentially using Flet), and add plotting for metrics.
3.  **Phase 3 & Beyond:** Explore more advanced concepts like GC-balanced encoding, simplified error correction codes (e.g., Hamming), batch processing, and potentially a plug-in API for new encoding schemes.

---

## Contributing

GeneCoder is envisioned as an open-source educational project. While development is just beginning, contributions will be very welcome in the future!

Once the foundational code is in place, look out for issues tagged `good first issue` or feel free to discuss your ideas by opening a new issue. (Detailed contribution guidelines will be added as the project matures).

---

## License

*(License to be determined and added here - likely MIT or Apache 2.0, aligning with open educational goals.)*

---

Happy Forging (or rather, Happy Coding)! We're excited to bring GeneCoder to life.
