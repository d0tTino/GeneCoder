# Implemented MVP Features

GeneCoder provides a CLI and GUI for encoding and decoding data into simulated DNA sequences. Key features include:

* **CLI for encoding and decoding** using multiple methods.
* **GC-Balanced encoding** with tunable constraints on [GC content](glossary.md#gc-content).
* **[Forward Error Correction](glossary.md#forward-error-correction-fec)** options such as Triple-Repeat, Hamming(7,4), Reed-Solomon and the optional FrameD C++ backend.
* **Parity checks** for additional error detection.
* **Batch processing** and streaming support for large files.
* **Flet-based GUI** with analysis plots and asynchronous operations.
* **Drag-and-drop file selection** on the Encode tab.
* **CSV export for synthesis** with length and [homopolymer](glossary.md#homopolymer) validation. The analysis command warns when sequences violate these constraints.
* **Mirror encoding** via `--mirror` to output forward and reverse-complement sequences.
* **Fix my sequence** button adjusts GC balance and homopolymers on the fly.


## Visualizer

The GUI now includes a **Visualizer** tab powered by a dedicated React
application under `web/helix-ui`. The visualization renders each nucleotide as a
colored sphere with tooltips. Orbit controls allow zooming and rotating. GC
content colouring and homopolymer highlighting are shown both on the helix and
via an overlay canvas. Animated pulses can move along the helix to illustrate
progress. The frontend is loaded on demand so it works in both desktop and web
deployments.
Encoding results automatically trigger the viewer so you can inspect the output
sequence right away.

![Visualizer tab GUI](https://flet.dev/docs/images/screenshot.png)

### Usage

Import `show_helix` and pass a DNA sequence. Optional `length` and `colors` arguments control the rendered sequence length and sphere colors:

```python
from genecoder.helix_view import show_helix
webview = show_helix("ACGT", length=50, colors={"A": "#ff0000", "T": "#00ffff"})
```

The newer `show_helix_ui` helper launches the React frontend. It accepts the
same base sequence along with options such as `animate`, `zoom`, `gc`, `runs`,
animated progress pulses and custom base colors. Pass a second sequence to
render two strands side by side:

```python
from genecoder.helix_view import show_helix_ui
webview = show_helix_ui(seq1, seq2)
```

The `--mirror` flag on the CLI writes both forward and reverse-complement
records which can be viewed together using `show_helix_ui` as above.

## DeepDNA Codec

GeneCoder includes an optional AI-based FEC backend wrapping the open-source DeepDNA model. Install the extra and use it just like the other FEC methods:

```bash
pip install "genecoder[deepdna]"
```

### Example usage

```python
from genecoder.deepdna_codec import encode_data_deepdna, decode_data_deepdna

data = b"hello world"
encoded, info = encode_data_deepdna(data)
decoded, _ = decode_data_deepdna(encoded, info)
```

## Sequence Design Interface

Browse to `/design` on the running server to access a small tool for validating and fixing short DNA sequences. Enter a sequence and click **Validate** to call `/design/validate`; the response shows whether the sequence is within the GC and homopolymer limits. Press **Fix** to invoke `/design/fix`, which returns an adjusted sequence that satisfies the constraints. The updated sequence and metrics are displayed underneath the buttons.
