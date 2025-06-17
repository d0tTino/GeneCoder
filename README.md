# GeneCoder

[![Documentation](https://img.shields.io/badge/docs-online-blue)](https://d0ttino.github.io/GeneCoder/)

GeneCoder is an educational toolkit for exploring DNA-based data storage. It provides a command line interface and a GUI for encoding and decoding files into simulated DNA sequences.

For full usage instructions and additional documentation see the [docs/](docs/) directory or the hosted documentation linked above.
For instructions on launching the GUI see the [usage guide](docs/usage.md#launching-the-flet-app).

## Features

- Multiple encoding strategies including Base-4 Direct, Huffman-4 and GC-Balanced.
- Optional error correction with Triple-Repeat, Hamming(7,4), Reed-Solomon, LDPC and Fountain codes.
- Batch processing, parity checks and streaming support.
- Flet-based GUI with analysis plots.

## Quick Install

```bash
pip install -r requirements.txt
pip install .[gui]  # install GUI extras when desired
```

Desktop packages are available on the [releases page](https://github.com/d0tTino/GeneCoder/releases).
Download the `.msix` file for Windows or the `.dmg` for macOS and follow your
platform's standard installation prompts.

To run the web build locally install the optional `web` extras and start the
FastAPI server:

```bash
pip install .[web]
uvicorn web.main:app --reload
```

See [docs/installation.md](docs/installation.md) for detailed setup and testing instructions, including the [mamba-based setup](docs/installation.md#mamba-based-setup) and the [Windows Quick Start](docs/installation.md#windows-quick-start).

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

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

GeneCoder is released under the [MIT License](LICENSE).

See [CITATION.cff](CITATION.cff) for citation information.

### Plugins

GeneCoder can be extended through plugins discovered via the
`genecoder.plugins` entry point. See [docs/plugins.md](docs/plugins.md) for
details on writing and registering new codecs or viewers.
