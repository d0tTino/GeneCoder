# Advanced FEC Example

This sample package demonstrates how to provide a custom LDPC
forward error correction plugin for GeneCoder. It reuses the
built-in LDPC helpers from the `genecoder.ldpc_codec` module and
exposes them under the entry point `advanced_ldpc`.

## Installation

Install the package from the repository root:

```bash
pip install ./plugins-examples/advanced_fec
```

The LDPC implementation relies on optional dependencies. Install
GeneCoder with the `ldpc` extra to enable them:

```bash
pip install 'genecoder[ldpc]'
```

## Usage

After installation simply import GeneCoder (or invoke the CLI) to
load the plugin automatically. The new FEC backend will appear in
`genecoder.plugins.FEC_REGISTRY` under the name `advanced_ldpc`.
