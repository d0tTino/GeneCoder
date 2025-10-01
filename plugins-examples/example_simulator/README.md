# Example Simulator Plugin

A passthrough simulator named `example`. The implementation now operates on
``SequenceBatch`` inputs and annotates each oligo with simulator coverage
metadata.

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

3. Run the simulator through the pipeline CLI and inspect the emitted metadata:

   ```bash
   genecli pipeline input.bin output.bin --codec base4_direct --channel example
   genecli bundle inspect output.bin --show-metadata | grep sim_
   ```
