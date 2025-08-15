# Advanced FEC Example

This sample package demonstrates how to provide a custom LDPC
forward error correction plugin for GeneCoder. It reuses the
built-in LDPC helpers from the `genecoder.ldpc_codec` module and
exposes them under the entry point `advanced_ldpc`.

## Step-by-step Usage

1. Install the package from the repository root:

   ```bash
   pip install ./plugins-examples/advanced_fec
   ```

2. Install GeneCoder with LDPC extras so the helper libraries are available:

   ```bash
   pip install 'genecoder[ldpc]'
   ```

3. Import GeneCoder to load the plugin and confirm registration:

   ```python
   from genecoder.plugins import load_plugins
   load_plugins()
   from genecoder import FEC_REGISTRY
   print("advanced_ldpc" in FEC_REGISTRY)
   ```

The package registers an `advanced_ldpc` backend within
`genecoder.plugins.FEC_REGISTRY`.
