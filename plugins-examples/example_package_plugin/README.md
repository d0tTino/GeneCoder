# Package Plugin Example

This sample package registers a simple codec using the generic
`genecoder.plugins` entry point group.

## Step-by-step Usage

1. Install the package from the repository root:

   ```bash
   pip install ./plugins-examples/example_package_plugin
   ```

2. Load plugins and confirm registration:

   ```python
   from genecoder.plugins import load_plugins
   load_plugins()
   from genecoder import CODEC_REGISTRY
   print("package_example" in CODEC_REGISTRY)
   ```

3. Encode data with the new codec via the CLI:

   ```bash
   genecli encode --method package_example --input-files data.txt --output-file out.fasta
   ```
