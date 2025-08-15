# Example Visualizer Plugin

A trivial visualizer named `example`.

## Step-by-step Usage

1. Install the package:

   ```bash
   pip install ./plugins-examples/example_visualizer
   ```

2. Load plugins and ensure the visualizer is registered:

   ```python
   from genecoder.plugins import load_plugins
   load_plugins()
   from genecoder import VISUALIZER_REGISTRY
   print("example" in VISUALIZER_REGISTRY)
   ```

3. Invoke the visualizer from Python:

   ```python
   VISUALIZER_REGISTRY["example"]("ACGT")
   ```
