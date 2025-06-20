# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
- Continuous improvements to CI workflows and build configuration.
- Added packaging metadata for PyPI distribution.
- CLI/GUI option ``--alphabet`` supporting ``base4``, ``base5`` and ``base6``.
- Fixed plugin registration during package installation.
- Pinned dependencies to stable versions.
- ``encode_gc_balanced`` now validates the inverted sequence and logs a warning
  if it still violates GC content or homopolymer limits.

## [0.1.0] - 2025-06-12
### Added
- Command-line interface for encoding and decoding data.
- Base-4 direct mapping and Huffman encoding methods.
- GC-balanced encoder with homopolymer and GC content constraints.
- Forward error correction options: Triple-Repeat, Hamming(7,4), and Reed-Solomon.
- Parity-based error detection.
- Flet-based graphical user interface with asynchronous operations.
- Metrics reporting and analysis plots.
