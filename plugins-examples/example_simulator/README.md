# Example Simulator Plugin

A passthrough simulator named `example`.

## Step-by-step Usage

1. Install the package:

   ```bash
   pip install ./plugins-examples/example_simulator
   ```

2. Load plugins and verify the simulator registered:

   ```python
   from genecoder.plugins import load_plugins
   load_plugins()
   from genecoder.simulators import SIMULATOR_REGISTRY
   print("example" in SIMULATOR_REGISTRY)
   ```

3. Run the simulator through the pipeline CLI:

   ```bash
   genecli pipeline input.bin output.bin --codec base4_direct --channel example
   ```
