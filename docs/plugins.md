# Plugin development guide

This document explains how to extend GeneCoder with custom codecs, FEC backends, simulators, and visualizers. It covers the registry APIs in `src/genecoder/plugin_manager.py`, how to package plugins as Python entry points, and the security controls applied when loading third-party code.

## Overview of plugin types

GeneCoder exposes four plugin interfaces defined in [`genecoder.api`](../src/genecoder/api.py):

- **Codecs** implement `encode(data: bytes, **kwargs) -> str` and `decode(encoded: SequenceBatch | str, **kwargs) -> bytes`.
- **FEC backends** implement `encode(data: bytes, **kwargs) -> tuple[bytes, Mapping[str, Any]]` and `decode(encoded: bytes, info: Mapping[str, Any], **kwargs) -> tuple[bytes, int]`.
- **Simulators** implement `simulate(sequence: str | SequenceBatch) -> str | SequenceBatch` and can optionally override `with_profile(profile: str) -> Simulator` for profile-aware variants.
- **Visualizers** implement `visualize(sequence: str, **kwargs) -> Any`.

Registries for each interface live in [`genecoder.plugin_manager`](../src/genecoder/plugin_manager.py) and are populated by built-in plugins, Python entry points, and optional local modules. Later registrations override earlier ones, letting users replace bundled defaults with custom implementations.

## Writing a plugin module

A plugin module must expose registration helpers that accept the corresponding registry function. Each registry helper receives the appropriate registrar (for example, `register_codec`) and should call it with a unique name and an object that implements the required interface.

```python
# plugins/my_codec.py
from genecoder.api import Codec

class MyCodec(Codec):
    def encode(self, data: bytes, **kwargs) -> str:
        return data.decode().replace("0", "A")

    def decode(self, encoded: str, **kwargs) -> bytes:
        return encoded.replace("A", "0").encode()

def register(register_codec):
    register_codec("my_codec", MyCodec)
```

The registrar accepts either an instance or a subclass of the interface. The plugin manager instantiates classes and validates method signatures before adding them to the registry.

### Supporting multiple interfaces

A single module can expose multiple registration helpers. The plugin manager looks for the following callables:

- `register(register_codec)` for codecs
- `register_fec(register_fec)` for FEC backends
- `register_simulator(register_simulator)` for simulators
- `register_visualizer(register_visualizer)` for visualizers

Implement only the helpers you need; missing helpers are ignored.

## Packaging entry point plugins

GeneCoder discovers plugins registered under the following entry point groups:

- `genecoder.plugins` (codecs)
- `genecoder.fec` (FEC backends)
- `genecoder.simulators`
- `genecoder.visualizers`

Add entry points to your `pyproject.toml` so they are installed with your package:

```toml
[project]
name = "genecoder-my-plugins"
version = "0.1.0"

[project.entry-points."genecoder.plugins"]
my_codec = "my_package.plugins.my_codec"

[project.entry-points."genecoder.simulators"]
my_channel = "my_package.plugins.my_simulator"
```

Each entry point value should point to the module that defines your `register_*` helpers. During startup GeneCoder imports these entry points and calls the appropriate helper to populate the registry. When `GENECODER_OFFLINE=1` is set, entry points are lazily imported: placeholders are registered first, and the module is imported only when the plugin name is accessed.

## Exposing plugin metadata

Plugins may provide a `PLUGIN_METADATA` dictionary with the following fields:

```python
PLUGIN_METADATA = {
    "name": "my_codec",           # unique plugin name
    "version": "0.1.0",           # semantic version string
    "interfaces": ["codec"],       # one or more of: codec, FEC, simulator, visualizer
}
```

Metadata is optional but recommended so GeneCoder can report compatibility information and detect duplicates when building a plugin catalog.

## Loading local plugins for development

For rapid iteration, add a `plugins/` package alongside your project root:

```
/your-repo
├─ plugins/
│  └─ my_codec.py
└─ pyproject.toml
```

Modules inside `plugins/` are discovered by `load_local_plugins()` without packaging. Define the same `register_*` helpers described above. This is useful for testing plugins before publishing them as installable packages.

## Example: implementing a simulator with profiles

```python
# plugins/my_simulator.py
from genecoder.api import Simulator

class MySimulator(Simulator):
    def __init__(self, error_rate: float = 0.01):
        self.error_rate = error_rate

    def simulate(self, sequence, /):
        # replace the last nucleotide to mimic an error
        return sequence[:-1] + "G"

    def with_profile(self, profile: str):
        if profile == "high_error":
            return MySimulator(error_rate=0.05)
        raise NotImplementedError("unknown profile")

def register_simulator(registrar):
    registrar("my_simulator", MySimulator)
```

Add the simulator to your package entry points under `genecoder.simulators` to make it available via CLI flags (for example, `--simulator my_simulator`).

## Security and trusted sources

Loading external plugins executes arbitrary Python code. GeneCoder provides several controls to help manage risk:

- **Network opt-in:** package downloads from registry URLs are blocked unless `GENECODER_ALLOW_NETWORK=1` is set. Setting `GENECODER_OFFLINE=1` forces offline mode even if network access is allowed.
- **Signature and checksum verification:** registry entries can include a Base64 signature (`signature`) and checksum (`checksum`). Signatures are verified using the public key specified in `GENECODER_PLUGIN_PUBLIC_KEY`. Failing verification aborts installation.
- **Safe URLs and packages:** plugin registry entries are validated to ensure package names and URLs match safe patterns.
- **Duplicate protection:** the plugin catalog rejects duplicate names to avoid silently overriding unrelated plugins.

Only install plugins from sources you trust, and prefer signed packages when distributing plugins externally.

## Troubleshooting

- If a plugin fails to import, start GeneCoder with `GENECODER_OFFLINE=1` to defer loading and inspect error messages when the plugin is first used.
- Ensure entry point names match the registry key you expect to use in CLI options and configuration files.
- Validate `PLUGIN_METADATA.interfaces` matches the helpers you provide so the catalog reflects the plugin accurately.
