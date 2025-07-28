# Plugin System

GeneCoder discovers additional functionality using Python entry points. Any
package can expose entry points under `genecoder.plugins`, `genecoder.fec` or
`genecoder.simulators` that point to modules with a `register` function. The
function receives a callback used to add the implementation to the appropriate
registry. GeneCoder looks only at packages installed in your current Python
environment when loading plugins.

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

Visualizer plugins register under `genecoder.visualizers` with a
`register_visualizer` callback. The class should implement the
``genecoder.api.Visualizer`` interface.

```toml
[project.entry-points."genecoder.visualizers"]
myvis = "my_package.my_vis"
```

```python
from genecoder.api import Visualizer

class MyVisualizer(Visualizer):
    def visualize(self, sequence: str, /, **kwargs):
        ...

def register(register_visualizer):
    register_visualizer("myvis", MyVisualizer())
```

Registered codecs are available via `genecoder.CODEC_REGISTRY` after importing
GeneCoder.

## Plugin Security

Installing a plugin runs code from a third-party package. Always verify
downloads and use registries from trusted sources. GeneCoder can validate a
wheel's digital signature with
:func:`genecoder.plugin_security.verify_signature`, which internally calls
:func:`genecoder.security.compute_checksum` and raises ``InvalidSignature`` if
verification fails. Set the ``GENECODER_PLUGIN_PUBLIC_KEY`` environment variable
to the path of a PEM encoded key so the installer can perform this check
automatically.

Host registry files over HTTPS or a secured internal server and keep them under
version control. Each entry should include a ``checksum`` or ``signature`` so
tampering is detected before installation.

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
generated template registers an entry point and includes a README explaining
how to install the distribution locally for development.

## Developing a Plugin Step by Step

1. Copy `src/plugins/reverse_codec.py` as a starting point.
2. Implement a class with `encode` and `decode` methods for your algorithm.
3. In the module's `register()` function call `register_codec` with a unique name.
4. Add an entry under `genecoder.plugins` in the `[project.entry-points]`
   section of your `pyproject.toml` pointing to the module.
5. Install the package and run `python -m genecoder.plugins` or invoke the CLI to load it.

GeneCoder loads plugins only from installed packages. After installing your
project locally, import GeneCoder or invoke the CLI to register the new plugin.
Registered codecs and simulators appear in the respective registries once
`genecoder.plugins.load_plugins()` runs.

## Plugin Registries

GeneCoder can install a set of third-party packages listed in a YAML registry.
Set the `GENECODER_PLUGIN_REGISTRY_URL` environment variable to the registry
file and run the install command below. If this variable is unset no network
requests are made and GeneCoder loads only plugins already present in the
current Python environment.

```bash
genecli plugin install-registry --allow-registry
```

The command reads the `packages` array from the YAML document and installs each
entry with `pip`. Entries may specify a `spec`, `package` or `url` value that is
passed directly to `pip install`. **Every entry must now include either a**
`checksum` **or a** `signature` **field**. When a `checksum` is provided the
downloaded wheel's SHA256 digest must match. A `signature` is validated using
the public key referenced by `GENECODER_PLUGIN_PUBLIC_KEY`.

Example registry:

```yaml
packages:
  - spec: https://example.com/mycodec-1.0-py3-none-any.whl
    checksum: "91b6d490..."
    signature: "MEUCIQDf..."
  - spec: myplugin==0.2.4
```

Installing plugins executes code from remote sources. Always verify checksums or
signatures and only use registry files from trusted providers. The
`--allow-registry` flag is required to opt in to this behaviour as a safety
measure and the command will fail without it.

Example environment setup:

```bash
export GENECODER_PLUGIN_REGISTRY_URL=https://example.com/plugins.yaml
export GENECODER_PLUGIN_PUBLIC_KEY=/path/to/public.pem
```


## Challenge Scoreboard

The GeneCoder web server exposes a small API for recording plugin challenge results. Scores can be retrieved with `GET /catalog/challenge` and new entries submitted via `POST /catalog/challenge`.

Set `GENECODER_API_TOKEN` to secure write access before starting the server:

```bash
export GENECODER_API_TOKEN=secret
uvicorn web.main:app
```

Submit a score with `curl` by including the token in the `Authorization` header:

```bash
curl -X POST http://localhost:8000/catalog/challenge \
  -H "Authorization: Bearer $GENECODER_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "alice", "points": 5}'
```

A React page in `web/helix-ui` displays the standings. After building the web assets open `helix-ui/scoreboard.html` (or `dist/scoreboard.html`) in a browser while the server is running to view the leaderboard.

