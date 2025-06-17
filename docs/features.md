# Implemented MVP Features

GeneCoder provides a CLI and GUI for encoding and decoding data into simulated DNA sequences. Key features include:

* **CLI for encoding and decoding** using multiple methods.
* **GC-Balanced encoding** with tunable constraints.
* **Forward Error Correction** options such as Triple-Repeat, Hamming(7,4) and Reed-Solomon.
* **Parity checks** for additional error detection.
* **Batch processing** and streaming support for large files.
* **Flet-based GUI** with analysis plots and asynchronous operations.

## Helix View

The GUI now includes a **Helix View** tab powered by a Three.js scene. The
visualization renders each nucleotide as a colored sphere with hover tooltips
showing the original byte information.  Orbit controls allow zooming and
rotating the helix.  The scene is loaded on demand so it works in both desktop
and web deployments.
