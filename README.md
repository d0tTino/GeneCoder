# GeneCoder

[![Documentation](https://img.shields.io/badge/docs-online-blue)](https://d0ttino.github.io/GeneCoder/)
[![Coverage Status](coverage.svg)](https://codecov.io/gh/d0tTino/GeneCoder)

GeneCoder is an educational toolkit for exploring DNA-based data storage. It provides a command line interface and a GUI for encoding and decoding files into simulated DNA sequences.

For full usage instructions and additional documentation see the [docs/](docs/) directory or the hosted documentation linked above.
For instructions on launching the GUI see the [usage guide](docs/usage.md#launching-the-flet-app).
For a quick end-to-end demo see [docs/vertical_slice.md](docs/vertical_slice.md).
Introductory Jupyter notebooks with encoding and decoding examples are available in the [notebooks/](notebooks) directory.
Step-by-step lesson notebooks covering encoding basics, FEC, simulators and analysis can be found in [notebooks/lessons](notebooks/lessons).

GeneCoder's long-term goal is to provide an integrated research platform that
bridges encoding algorithms with sequencing and synthesis simulations while
remaining easy to extend. The guiding ideas are summarized in
[docs/DEVELOPMENT_VISION.md](docs/DEVELOPMENT_VISION.md).

### Disclaimer

GeneCoder is intended for educational simulations only. It should not be used to
handle personal or medical DNA data.

## Features

- Multiple encoding strategies including Base-4 Direct, Huffman-4 and GC-Balanced.
- Optional error correction with Triple-Repeat, Hamming(7,4), Reed-Solomon, LDPC and Fountain codes.
- Batch processing, parity checks and streaming support.
- Resumable streaming for interrupted runs.
- Optional AI-driven decoding via the DNAformer plugin.
- Flet-based GUI with analysis plots and an enhanced 3D helix viewer.
- Base5 and base6 alphabet options for alternative nucleotide letters. These
  modes remap the standard ACGT symbols but **do not increase capacity**.
- External read simulators can be invoked with ``--simulator``.
   Extra parameters may be supplied via ``--d2sim-options``,
   ``--dnarsim-options`` or ``--squigulator-options``. The same values can be
   provided using the environment variables ``GENECODER_D2SIM_OPTIONS``,
   ``GENECODER_DNARSIM_OPTIONS`` and ``GENECODER_SQUIGULATOR_OPTIONS``.

## Quick Start

GeneCoder requires **Python 3.11+** and uses
[Poetry](https://python-poetry.org/) for dependency management. Install the
dependencies with:

```bash
poetry install --no-interaction
```

Install optional extras for the GUI or web API with:

```bash
poetry install --with gui,web --no-interaction
```

Additional plugins such as DNAformer or FrameD can be installed via
Poetry's ``--extras`` flag:

```bash
poetry install --extras dnaformer --extras framed --no-interaction
```


Desktop packages are available on the [releases page](https://github.com/d0tTino/GeneCoder/releases).
Download the `.msix` file for Windows or the `.dmg` for macOS and follow your
platform's standard installation prompts.

To run the web build locally install the optional `web` extras and start the
FastAPI server:

```bash
poetry install --with web --no-interaction
poetry run uvicorn web.main:app --reload
```

Set the `GENECODER_API_TOKEN` environment variable to supply the bearer token
required by the API. If the variable is not set, a random token is generated and
printed at startup.

See [docs/installation.md](docs/installation.md) for detailed setup and testing instructions, including the [mamba-based setup](docs/installation.md#mamba-based-setup) and the [Windows Quick Start](docs/installation.md#windows-quick-start).
- For a quick end-to-end demo see [docs/vertical_slice.md](docs/vertical_slice.md).
- For working inside the VS Code Dev Container see [docs/installation.md#using-the-dev-container](docs/installation.md#using-the-dev-container).

## Development Setup

Install the project in editable mode with development tools:

```bash
poetry install --with gui,web,dev --no-interaction
```

## OpenAI Testing Environment

The `openai_testing/` directory bundles the demo from the
[`openai-testing-agent-demo`](https://github.com/openai/openai-testing-agent-demo)
repository. It provides a CUA server, a sample application and a frontend UI
for automated interface tests. You will need Node.js, npm and an
`OPENAI_API_KEY` set in your environment. To start the demo and launch the
GeneCoder Flet GUI run:

```bash
make openai-testing
```

See [openai_testing/README.md](openai_testing/README.md) for full details.

## Continuous Integration

GitHub Actions run linting and tests whenever source code changes. Documentation
or comment-only updates skip the heavy jobs, keeping CI usage efficient.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

GeneCoder is released under the [MIT License](LICENSE).

See [CITATION.cff](CITATION.cff) for citation information.

### Plugins

GeneCoder can be extended through plugins discovered via the
`genecoder.plugins`, `genecoder.fec` and `genecoder.simulators` entry points.
See [docs/plugins.md](docs/plugins.md) for details on writing and registering
new codecs, FEC back-ends or simulators. Plugins are automatically loaded when
using the CLI or GUI. When using GeneCoder as a library call
``genecoder.plugins.load_plugins()`` first to populate the registries.
