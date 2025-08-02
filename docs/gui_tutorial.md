# GUI Tutorial

This tutorial shows how to launch the Flet-based graphical interface.

## Installation

```bash
pip install genecoder[gui]
```
This installs the optional `gui` extras which pull in Flet, Matplotlib and
`flet-webview`.

## Running the application

```bash
python -m genecoder.flet_app
```

The application window contains three main tabs:

1. **Encode** – choose an input file, encoding method and optional FEC.
2. **Decode** – select a FASTA file to decode and configure error simulation.
3. **Visualizer** – render the resulting DNA sequence in 3D. See the
   [Helix Frontend guide](helix_frontend.md) for viewer options.

The Encode tab includes a **Mirror** checkbox to output the reverse-complement
alongside the main sequence. Toggle this on to view both strands together in the
Visualizer.
Drag files onto the Encode tab or use the **Browse File** button to select an
input file.

![GUI screenshot](https://flet.dev/docs/images/screenshot.png)

Use the buttons at the bottom of each tab to start the selected operation.

After encoding completes, GC and homopolymer metrics are shown. If they fall outside recommended ranges, a **Fix Sequence** button allows automatic adjustment. Clicking it displays the fixed DNA snippet and updated metrics.

Example: encode any file, then click **Fix Sequence** when the suggestion text appears to view the corrected sequence.

## Launching the Streamlit Dashboard

GeneCoder also ships with a simple Streamlit dashboard for exploring simulation metrics. After installing the `gui` extras, run:

```bash
genecli dashboard examples/dashboard_metrics.json
```

The dashboard visualizes the sample metrics file and plots GC distribution, homopolymer statistics and decode success rates.
