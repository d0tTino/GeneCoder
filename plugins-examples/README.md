# Plugin Examples

This directory contains minimal example plugins demonstrating how to integrate
custom codecs, FEC implementations, visualizers and read simulators with GeneCoder.
The simulator templates now showcase the ``genecoder.formats.SequenceBatch``
API, including how to surface batch identifiers, seeds and coverage metrics
through oligo metadata.

Each subdirectory is an installable Python package using PEP 621 metadata:

- `example_codec` – registers a codec named `example`.
- `example_fec` – registers a FEC backend named `example`.
- `example_simulator` – registers a simulator named `example` that returns a
  full ``SequenceBatch`` with coverage statistics in the metadata.
- `example_visualizer` – registers a visualizer named `example`.
- `advanced_fec` – registers an LDPC FEC backend named `advanced_ldpc`.

Install any of the packages with `pip` to experiment locally, e.g.:

```bash
pip install ./plugins-examples/example_codec
```

All templates depend on `genecoder>=0.2.0` so batch-aware metadata helpers are
available when you install them into a custom environment.
