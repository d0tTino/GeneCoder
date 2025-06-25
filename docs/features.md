# Implemented MVP Features

GeneCoder provides a CLI and GUI for encoding and decoding data into simulated DNA sequences. Key features include:

* **CLI for encoding and decoding** using multiple methods.
* **GC-Balanced encoding** with tunable constraints.
* **Forward Error Correction** options such as Triple-Repeat, Hamming(7,4), Reed-Solomon and the optional FrameD C++ backend.
* **Parity checks** for additional error detection.
* **Batch processing** and streaming support for large files.
* **Flet-based GUI** with analysis plots and asynchronous operations.
* **CSV export for synthesis** with length and homopolymer validation. The analysis command warns when sequences violate these constraints.


## Helix View

The GUI now includes a **Helix View** tab powered by a dedicated React
application under `web/helix-ui`. The visualization renders each nucleotide as a
colored sphere with tooltips. Orbit controls allow zooming and rotating. GC
content colouring and homopolymer highlighting are shown both on the helix and
via an overlay canvas. Animated pulses can move along the helix to illustrate
progress. The frontend is loaded on demand so it works in both desktop and web
deployments.

![Helix View GUI](https://flet.dev/docs/images/screenshot.png)

### Usage

Import `show_helix` and pass a DNA sequence. Optional `length` and `colors` arguments control the rendered sequence length and sphere colors:

```python
from genecoder.helix_view import show_helix
webview = show_helix("ACGT", length=50, colors={"A": "#ff0000", "T": "#00ffff"})
```

The newer `show_helix_ui` helper launches the React frontend. It accepts the
same base sequence along with options such as `animate`, `zoom`, `gc`, `runs`,
animated progress pulses and custom base colors.
