# Example FEC Plugin

A minimal forward error correction plugin named `example`.

## Step-by-step Usage

1. Install the package:

   ```bash
   pip install ./plugins-examples/example_fec
   ```

2. Load plugins and verify registration:

   ```python
   from genecoder.plugins import load_plugins
   load_plugins()
   from genecoder import FEC_REGISTRY
   print("example" in FEC_REGISTRY)
   ```

3. Use the FEC module during encoding:

   ```bash
   genecli encode --method base4_direct --fec example --input-files data.txt --output-file out.fasta
   ```
