# Implemented MVP Features

GeneCoder provides a CLI and GUI for encoding and decoding data into simulated DNA sequences. Key features include:

* **CLI for encoding and decoding** using multiple methods.
* **GC-Balanced encoding** with tunable constraints.
* **Forward Error Correction** options such as Triple-Repeat, Hamming(7,4) and Reed-Solomon.
* **Parity checks** for additional error detection.
* **Batch processing** and streaming support for large files.
* **Flet-based GUI** with analysis plots and asynchronous operations.

## Helix View

The GUI now includes a **Helix View** tab powered by a small Three.js scene. Select the tab to load a rotating DNA helix rendered inside the application. This is implemented using an `HtmlElement` so it works in both desktop and web deployments. The screenshot is omitted in this repository.

To view the helix, open the *Helix View* tab in the GUI. The visualization loads on demand and does not block other tabs.
