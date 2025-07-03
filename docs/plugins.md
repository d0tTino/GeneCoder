# Plugin System

GeneCoder discovers additional functionality using Python entry points. Any
package can expose entry points under `genecoder.plugins`, `genecoder.fec` or
`genecoder.simulators` that point to modules with a `register` function. The
function receives a callback used to add the implementation to the appropriate
registry.

Example `pyproject.toml` snippet:

```toml
[project.entry-points."genecoder.plugins"]
mycodec = "my_package.my_plugin"
```

And the plugin module:

```python
# my_package/my_plugin.py

def register(register_codec):
    def encode(data: bytes) -> str:
        ...
    def decode(text: str) -> bytes:
        ...
    register_codec("mycodec", encode, decode)
```

To add a custom [FEC](glossary.md#forward-error-correction-fec) implementation you would use the `genecoder.fec` group and
call the provided `register_fec` callback:

```toml
[project.entry-points."genecoder.fec"]
myfec = "my_package.my_fec"
```

```python
# my_package/my_fec.py

def register(register_fec):
    def encode(data: bytes):
        ...
    def decode(encoded: bytes, info):
        ...
register_fec("myfec", encode, decode)
```

Simulator plugins follow the same pattern using the `genecoder.simulators`
group with a `register_simulator` callback that receives an object implementing
the :class:`genecoder.channels.base.BaseChannel` protocol.

Registered codecs are available via `genecoder.CODEC_REGISTRY` after importing
GeneCoder.

## Built-in Plugins

GeneCoder includes a set of codec, FEC and simulator plugins that ship with the
project. These are registered when :func:`genecoder.plugins.load_plugins` imports
the :mod:`genecoder.builtin_plugins` module before discovering any third-party
extensions.

## Plugin Examples

See the [plugins-examples](../plugins-examples/) directory in the source tree for
minimal sample packages implementing a codec, a
[FEC](glossary.md#forward-error-correction-fec) backend, a read
simulator and a small package plugin using the `genecoder.plugins`
group. Install any of these packages with `pip install` to experiment
with custom extensions locally.

## Developing a Plugin Step by Step

1. Copy `src/plugins/reverse_codec.py` as a starting point.
2. Implement `encode` and `decode` functions for your algorithm.
3. In the module's `register()` function call `register_codec` with a unique name.
4. Add an entry under `genecoder.plugins` in the `[project.entry-points]`
   section of your `pyproject.toml` pointing to the module.
5. Install the package and run `python -m genecoder.plugins` or invoke the CLI to load it.

## Installing Third-Party Plugins

Plugins are discovered via Python entry points, so any installed package that
defines the appropriate entry point will be loaded automatically. Install a
plugin from PyPI:

```bash
pip install genecoder-myplugin
```

Or from a local directory:

```bash
pip install ./path/to/my_plugin
```

After installation, import GeneCoder or invoke the CLI to load the new plugin.
Registered codecs and simulators appear in the respective registries:

```python
import genecoder
from genecoder.plugins import CODEC_REGISTRY

genecoder.plugins.load_plugins()
print(CODEC_REGISTRY.keys())
```

## Plugin Registries

`load_plugins()` can optionally install third‑party plugins from a remote
registry before discovering entry points. Set the environment variable
`GENECODER_PLUGIN_REGISTRY_URL` to the location of a YAML file listing plugin
packages:

```yaml
packages:
  - genecoder-fancy-plugin>=1.0
  - git+https://example.com/user/custom.git
```

The URL may use HTTP(S) or point to a local file via ``file://``. Each entry is
passed directly to ``pip install``. Only use registries from trusted sources as
their packages are installed and executed automatically.

### Security Considerations

When ``GENECODER_PLUGIN_REGISTRY_URL`` is set, GeneCoder will prompt for
confirmation before installing each package from the registry. Review the list
of packages carefully and only accept installations from sources you trust.
Consider verifying a digital signature for the registry file or each package
before proceeding.
