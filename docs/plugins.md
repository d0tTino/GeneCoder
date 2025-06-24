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

To add a custom FEC implementation you would use the `genecoder.fec` group and
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
minimal sample packages implementing a codec, a FEC backend and a read
simulator. Install any of these packages with `pip install` to experiment with
custom extensions locally.
