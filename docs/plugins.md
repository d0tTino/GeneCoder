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
from genecoder.api import Codec

class MyCodec(Codec):
    def encode(self, data: bytes) -> str:
        ...

    def decode(self, text: str) -> bytes:
        ...

def register(register_codec):
    register_codec("mycodec", MyCodec)
```

## Package Structure

A plugin is a standard Python package. At a minimum it contains a
`pyproject.toml` declaring the entry point and a module with a
`register()` function. The directory layout for a project named
`mycodec` could look like this:

```text
mycodec/
├── pyproject.toml
└── mycodec/
    └── __init__.py
```

The `__init__.py` file defines the codec class and the `register`
function shown above.

To add a custom [FEC](glossary.md#forward-error-correction-fec) implementation you would use the `genecoder.fec` group and
call the provided `register_fec` callback:

```toml
[project.entry-points."genecoder.fec"]
myfec = "my_package.my_fec"
```

```python
# my_package/my_fec.py
from genecoder.api import FEC

class MyFEC(FEC):
    def encode(self, data: bytes):
        ...

    def decode(self, encoded: bytes, info):
        ...

def register(register_fec):
    register_fec("myfec", MyFEC)
```

Simulator plugins follow the same pattern using the `genecoder.simulators`
group with a `register_simulator` callback that receives an object implementing
the :class:`genecoder.api.Simulator` interface.

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

Run `scripts/scaffold_plugin.sh <name>` to create a new plugin project. The
generated template registers an entry point and includes a README with
instructions on signing the distribution.

## Signing Plugins

Third-party plugins distributed through the upcoming marketplace must be
signed. The helper scripts in `plugins-examples/signing/` show how to
generate an RSA key pair and attach the signature to your wheel. Publish
the `public.pem` key alongside the wheel so users can verify it.

## Developing a Plugin Step by Step

1. Copy `src/plugins/reverse_codec.py` as a starting point.
2. Implement a class with `encode` and `decode` methods for your algorithm.
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

