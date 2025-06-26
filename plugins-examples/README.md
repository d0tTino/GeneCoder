# Plugin Examples

This directory contains minimal example plugins demonstrating how to integrate
custom codecs, FEC implementations and read simulators with GeneCoder.

Each subdirectory is an installable Python package using PEP 621 metadata:

- `example_codec` – registers a codec named `example`.
- `example_fec` – registers a FEC backend named `example`.
- `example_simulator` – registers a simulator named `example`.
- `advanced_fec` – registers an LDPC FEC backend named `advanced_ldpc`.

Install any of the packages with `pip` to experiment locally, e.g.:

```bash
pip install ./plugins-examples/example_codec
```
