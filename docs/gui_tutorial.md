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
3. **Helix View** – render the resulting DNA sequence in 3D. See the
   [Helix Frontend guide](helix_frontend.md) for viewer options.

The Encode tab includes a **Mirror** checkbox to output the reverse-complement
alongside the main sequence. Toggle this on to view both strands together in the
Helix View.

![GUI screenshot](https://flet.dev/docs/images/screenshot.png)

Use the buttons at the bottom of each tab to start the selected operation.
