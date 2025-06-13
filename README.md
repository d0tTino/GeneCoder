# GeneCoder

[![Documentation](https://img.shields.io/badge/docs-online-blue)](https://d0ttino.github.io/GeneCoder/)

GeneCoder is an educational toolkit for exploring DNA-based data storage. It provides a command line interface and a GUI for encoding and decoding files into simulated DNA sequences.

For full usage instructions and additional documentation see the [docs/](docs/) directory or the hosted documentation linked above.

## Features

- Multiple encoding strategies including Base-4 Direct, Huffman-4 and GC-Balanced.
- Optional error correction with Triple-Repeat, Hamming(7,4) and Reed-Solomon.
- Batch processing, parity checks and streaming support.
- Flet-based GUI with analysis plots.

## Quick Install

```bash
pip install -r requirements.txt
```

See [docs/installation.md](docs/installation.md) for detailed setup and testing instructions.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

GeneCoder is released under the [MIT License](LICENSE).
