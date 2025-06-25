# GUI Tutorial

This tutorial shows how to launch the Flet-based graphical interface.

## Installation

```bash
pip install genecoder[gui]
```

## Running the application

```bash
python -m genecoder.flet_app
```

The application window contains three main tabs:

1. **Encode** – choose an input file, encoding method and optional FEC.
2. **Decode** – select a FASTA file to decode and configure error simulation.
3. **Helix View** – render the resulting DNA sequence in 3D.

![GUI screenshot](https://flet.dev/docs/images/screenshot.png)

Use the buttons at the bottom of each tab to start the selected operation.
