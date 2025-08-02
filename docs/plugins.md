# Plugin System

GeneCoder discovers additional functionality using Python entry points. Any
package can expose entry points under `genecoder.plugins`, `genecoder.fec` or
`genecoder.simulators` that point to modules with a `register` function. The
function receives a callback used to add the implementation to the appropriate
registry. GeneCoder looks only at packages installed in your current Python
environment when loading plugins.

## Entry Point Groups

The callback passed to `register()` depends on the entry point group used:

- **Codecs** register under `genecoder.plugins` and call
  `register_codec(name, CodecClass)`.
- **FEC modules** register under `genecoder.fec` and call
  `register_fec(name, FECClass)`.
- **Simulators** register under `genecoder.simulators` and call
  `register_simulator(name, SimulatorInstance)`.

See the packages in [`plugins-examples`](../plugins-examples/) for working
implementations of each entry point group.

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
automatically. Every wheel is hashed and the digest compared against the
``checksum`` or ``signature`` listed in the registry before installation.

When installing a signed wheel the file is downloaded and its SHA256 digest
computed. The signature from the registry entry is base64 decoded and verified
against the digest using the public key. Installation is aborted if this check
fails or if the digest does not match the optional ``checksum`` field.

Host registry files over HTTPS or a secured internal server and keep them under
version control. Each entry should include a ``checksum`` or ``signature`` so
tampering is detected before installation.

## Built-in Plugins

GeneCoder includes a set of codec, FEC and simulator plugins that ship with the
project. These are registered when :func:`genecoder.plugins.load_plugins` imports
the :mod:`genecoder.builtin_plugins` module before discovering any third-party
extensions.

The optional ``dnachisel_fixer`` plugin exposes a GC and homopolymer adjustment
helper powered by [DNA Chisel](https://github.com/Edinburgh-Genome-Foundry/DNAChisel).
Install GeneCoder with the ``chisel`` extras to enable it:

```bash
poetry install --extras chisel --no-interaction
```

## Plugin Examples

See the [plugins-examples](../plugins-examples/) directory in the source tree for
minimal packages showing how each entry point group works:

- `example_codec` – registers a codec using `register_codec("example", ExampleCodec)`.
- `example_fec` – registers a FEC backend via `register_fec("example", ExampleFEC)`.
- `example_simulator` – registers a simulator with `register_simulator("example", PassthroughChannel())`.
- `advanced_fec` – registers LDPC helper functions under `genecoder.fec`.
- `example_package_plugin` – demonstrates a small plugin that exposes simple
  encode/decode functions through `genecoder.plugins`.

Install any of these packages with `pip install ./plugins-examples/<name>` to
experiment locally.

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
Set the `GENECODER_PLUGIN_REGISTRY_URL` environment variable to point to that
registry file and run the install command below. The path may be an HTTP(S)
address or a local `file://` URL. When the variable is unset no network
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
the public key referenced by `GENECODER_PLUGIN_PUBLIC_KEY` and verified with
``genecoder.plugin_security.compute_checksum``.

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

### Verifying Plugin Signatures

Set the `GENECODER_PLUGIN_PUBLIC_KEY` environment variable to a PEM encoded
public key before running `genecli plugin install-registry --allow-registry`.
GeneCoder checks the `signature` field for every wheel using the helper
functions in [src/genecoder/plugin_checks.py](../src/genecoder/plugin_checks.py).

```bash
export GENECODER_PLUGIN_PUBLIC_KEY=/path/to/public.pem
genecli plugin install-registry --allow-registry
```

### Signing Plugin Packages

You can sign plugin wheels so GeneCoder verifies them during installation.

1. **Build the wheel**:
   ```bash
   python -m build
   ```
2. **Generate a private/public RSA key pair**:
   ```bash
   openssl genpkey -algorithm RSA -out private.pem -pkeyopt rsa_keygen_bits:2048
   openssl rsa -in private.pem -pubout -out public.pem
   ```
3. **Sign the wheel's SHA256 digest** and save the base64 encoded signature:
   ```bash
   openssl dgst -sha256 -sign private.pem -binary dist/*.whl | base64 > signature.txt
   ```
4. **Update your registry** with the value from `signature.txt` and share
   `public.pem` with users so they can verify the download.

Set the `GENECODER_PLUGIN_PUBLIC_KEY` environment variable to point to this
`public.pem` before running the installation command:

```bash
export GENECODER_PLUGIN_PUBLIC_KEY=/path/to/public.pem
genecli plugin install-registry --allow-registry
```

GeneCoder will compute the digest of each wheel and validate it against the
provided signature during installation.

### Registry Installation Security

The registry file enumerates remote wheels along with a `checksum` or
`signature` for each entry. A checksum is the wheel's SHA256 digest. A
signature is generated by signing that digest with a private key. Set
`GENECODER_PLUGIN_PUBLIC_KEY` to the matching public key so GeneCoder can
verify signatures. Registry installation is disabled by default and the
`--allow-registry` flag is required to opt in. Always host registry files over
HTTPS and keep them under version control. See the sample file at
[`configs/registry.yaml`](../configs/registry.yaml).

Secure installation with public‑key verification:

```bash
export GENECODER_PLUGIN_REGISTRY_URL=./configs/registry.yaml
export GENECODER_PLUGIN_PUBLIC_KEY=/path/to/public.pem
genecli plugin install-registry --allow-registry
```
## Simulator Environment Variables

External simulator plugins can forward additional flags to their underlying
tools. Set `GENECODER_D2SIM_OPTIONS`, `GENECODER_DNARSIM_OPTIONS` or
`GENECODER_SQUIGULATOR_OPTIONS` to pass options to the respective simulator.
Use `GENECODER_SIM_SEED` to make runs reproducible. The CLI automatically
includes these values when invoking the simulator plugin.

## Plugin Catalogs

Catalog files list metadata for available plugins. Set
`GENECODER_PLUGIN_CATALOG_URL` to a JSON or YAML document describing each
plugin. If the catalog includes a top-level `signature` field GeneCoder verifies
it using the public key specified in `GENECODER_CATALOG_PUBLIC_KEY` before
updating the catalog. Any modification causes verification to fail.

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

