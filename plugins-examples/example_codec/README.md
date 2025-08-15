# Example Codec Plugin

This package registers a minimal codec named `example`.

## Step-by-step Usage

1. Install the package:

   ```bash
   pip install ./plugins-examples/example_codec
   ```

2. Load plugins and verify the codec is available:

   ```python
   from genecoder.plugins import load_plugins
   load_plugins()
   from genecoder import CODEC_REGISTRY
   print("example" in CODEC_REGISTRY)
   ```

3. Encode a file via the CLI using the plugin:

   ```bash
   genecli encode --method example --input-files data.txt --output-file out.fasta
   ```
