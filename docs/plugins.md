# Plugin System

GeneCoder discovers additional functionality using Python entry points. Any
package can expose a `genecoder.plugins` entry point that points to a module with
a `register` function. The function receives a `register_codec` callable used to
add new codecs to the registry.

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

Registered codecs are available via `genecoder.CODEC_REGISTRY` after importing
GeneCoder.
