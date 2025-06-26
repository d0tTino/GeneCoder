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

## Plugin Examples

See the [plugins-examples](../plugins-examples/) directory in the source tree for
minimal sample packages implementing a codec, a
[FEC](glossary.md#forward-error-correction-fec) backend and a read
simulator. Install any of these packages with `pip install` to experiment with
custom extensions locally.

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
