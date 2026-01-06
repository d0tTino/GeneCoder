# Plugin System

GeneCoder discovers additional functionality using Python entry points. Any
package can expose entry points under `genecoder.plugins`, `genecoder.fec`,
`genecoder.simulators` or `genecoder.visualizers` that point to modules with a
`register` function. The function receives a callback used to add the
implementation to the appropriate registry. GeneCoder looks only at packages
installed in your current Python environment when loading plugins. Plugins that
use the batch-aware simulator API must declare `genecoder>=0.2.0` in their
project metadata.

The registries themselves live in [`src/genecoder/plugin_manager.py`](../src/genecoder/plugin_manager.py).
Built-in plugins register first, followed by entry-point modules and finally
any explicitly loaded local modules. Later registrations override earlier ones,
so you can replace shipped defaults with custom implementations during
development.

Plugins may optionally expose a ``PLUGIN_METADATA`` mapping with ``name``,
``version`` and ``interfaces`` fields. The catalog and CLI surfaces use this
metadata to present compatibility details when multiple plugins provide the
same capability (for example, competing channel simulators).

## Interface Expectations

Each plugin module must expose a ``register`` function that receives a callback
for adding implementations to GeneCoder's registries. The plugin then invokes
that callback with a unique name and the implementation class or instance.

### Encoders

Encoder plugins subclass [``genecoder.api.Codec``](api_reference.md#genecoder.api.Codec)
and implement ``encode`` and ``decode`` methods:

```python
from genecoder.api import Codec
from genecoder.formats import SequenceBatch


class MyCodec(Codec):
    def encode(self, data: bytes, /, **kwargs: object) -> str:
        ...

    def decode(
        self,
        encoded: SequenceBatch | str,
        /,
        *,
        batch_metadata: dict[str, str] | None = None,
        oligo_metadata: list[dict[str, str]] | None = None,
        **kwargs: object,
    ) -> bytes:
        ...


def register(register_codec):
    register_codec("mycodec", MyCodec)
```

Annotating the ``encoded`` parameter with :class:`~genecoder.formats.SequenceBatch`
signals that the codec can operate on batches. When present GeneCoder passes the
full :class:`SequenceBatch` object along with convenience keyword arguments
containing ``batch_metadata`` and ``oligo_metadata`` dictionaries. Codecs that
prefer not to use type annotations may instead set ``accepts_sequence_batch =
True`` on the codec instance or class.

### Channels

Channel plugins subclass [``genecoder.api.Simulator``](api_reference.md#genecoder.api.Simulator)
and implement a ``simulate`` method that accepts and returns
``SequenceBatch`` instances. The helper demonstrates converting legacy string
inputs into batches so per-oligo metadata is always available:

```python
import secrets

from genecoder.api import Simulator
from genecoder.formats import SequenceBatch
from genecoder.simulators.batch_utils import (
    RESULT_COVERAGE_KEY,
    clone_batch,
    finalize_batch_statistics,
)


class MyChannel(Simulator):
    def simulate(self, sequence: str | SequenceBatch) -> SequenceBatch:
        batch = sequence if isinstance(sequence, SequenceBatch) else SequenceBatch.build(
            [("mychannel", sequence)],
            batch_id="mychannel",
            batch_seed=secrets.randbits(32),
        )

        mutated = clone_batch(batch)
        coverage_counts: list[int] = []
        dropouts: list[bool] = []
        synthesis_failures: list[bool] = []
        mutation_totals: list[tuple[int, int, int]] = []

        for source, oligo in zip(batch.oligos, mutated.oligos):
            oligo.sequence = source.sequence
            coverage_counts.append(1)
            dropouts.append(False)
            synthesis_failures.append(False)
            mutation_totals.append((0, 0, 0))
            oligo.metadata[RESULT_COVERAGE_KEY] = "1"

        finalize_batch_statistics(
            mutated,
            coverage_counts,
            dropouts,
            synthesis_failures,
            mutation_totals,
        )

        if mutated.seed is None:
            mutated.seed = secrets.randbits(32)
        mutated.metadata["sim_seed"] = str(mutated.seed)

        return mutated


def register(register_simulator):
    register_simulator("mychannel", MyChannel())
```

### FEC

Forward error correction back-ends implement
[``genecoder.api.FEC``](api_reference.md#genecoder.api.FEC) with ``encode`` and
``decode`` methods and register through the ``genecoder.fec`` entry point.

### Visualizers

Visualizer plugins subclass
[``genecoder.api.Visualizer``](api_reference.md#genecoder.api.Visualizer) and
provide a ``visualize`` method:

```python
from genecoder.api import Visualizer

class MyVisualizer(Visualizer):
    def visualize(self, data: bytes) -> None:
        ...

def register(register_visualizer):
    register_visualizer("myviz", MyVisualizer())
```

Register visualizers through the ``genecoder.visualizers`` entry point group.

## Writing and Registering Plugins

Use entry points to extend GeneCoder with custom encoders, channels or
visualizers. The general workflow is:

1. **Project layout** – start from one of the examples in
   [`plugins-examples`](../plugins-examples/) such as
   [`example_codec`](../plugins-examples/example_codec/),
   [`example_simulator`](../plugins-examples/example_simulator/) or
   [`example_visualizer`](../plugins-examples/example_visualizer/).
2. **Declare an entry point** in `pyproject.toml` under the appropriate group
   (e.g. ``genecoder.plugins`` or ``genecoder.visualizers``).
3. **Implement the plugin and register it** by defining a ``register`` function
   that invokes the callback provided by GeneCoder.
4. **Install the package and verify discovery** with the CLI:

   ```bash
   pip install ./myplugin
   genecli plugin list   # shows installed plugins
   ```

### Encoder Example

```python
from genecoder.api import Codec
from genecoder.formats import SequenceBatch


class MyCodec(Codec):
    def encode(self, data: bytes, /, **kwargs: object) -> str:
        ...

    def decode(
        self,
        encoded: SequenceBatch | str,
        /,
        *,
        batch_metadata: dict[str, str] | None = None,
        oligo_metadata: list[dict[str, str]] | None = None,
        **kwargs: object,
    ) -> bytes:
        ...


def register(register_codec):
    register_codec("mycodec", MyCodec)
```

### Channel Example

```python
import secrets

from genecoder.api import Simulator
from genecoder.formats import SequenceBatch


class MyChannel(Simulator):
    def simulate(self, sequence: str | SequenceBatch) -> SequenceBatch:
        if isinstance(sequence, SequenceBatch):
            return sequence
        return SequenceBatch.build(
            [("mychannel", sequence)],
            batch_id="mychannel",
            batch_seed=secrets.randbits(32),
        )


def register(register_simulator):
    register_simulator("mychannel", MyChannel())
```

### Visualizer Example

This minimal plugin prints the raw bytes it receives.

`myviz.py`

```python
from genecoder.api import Visualizer

class MyViz(Visualizer):
    def visualize(self, data: bytes) -> None:
        print(f"visualized: {data!r}")

def register(register_visualizer):
    register_visualizer("myviz", MyViz())
```

Declare the entry point in `pyproject.toml`:

```toml
[project.entry-points."genecoder.visualizers"]
myviz = "myviz"
```

Run the visualizer:

```bash
$ genecli visualize myviz - <<<"hi"
visualized: b'hi\n'
```

See [`plugins-examples`](../plugins-examples/) for complete reference implementations.

### Batch-aware Adapter Patterns

- **Legacy simulators** – wrap older ``str``-only simulators with
  ``genecoder.simulators.batch_utils.apply_legacy_simulator``. The helper
  iterates each oligo, updates coverage statistics and returns a complete
  ``SequenceBatch`` so the rest of the pipeline can remain batch-native.
- **Metadata helpers** – use ``clone_batch`` to duplicate the incoming batch
  before mutating oligos. After processing, call ``finalize_batch_statistics`` to
  populate aggregate metrics such as coverage histograms and dropout rates.
- **Validation hooks** – mypy treats the templates in ``plugins-examples`` as
  first-class code. Running ``mypy --config-file mypy.ini`` will flag protocol
  mismatches if ``simulate`` stops returning ``SequenceBatch`` objects or
  required metadata keys are missing from the examples.

### Step-by-step Example

The `scripts/scaffold_plugin.sh` helper creates a minimal project ready for
customization. Replace `mycodec` with your desired package name:

```bash
./scripts/scaffold_plugin.sh mycodec
```

The script writes a small `plugin.py` containing a `register` function. After
adding your encode/decode logic the module may look like:

```python
# mycodec/mycodec/plugin.py
from genecoder.api import Codec
from genecoder.formats import SequenceBatch


class MyCodec(Codec):
    def encode(self, data: bytes) -> str:
        return data.decode().upper()

    def decode(self, encoded: SequenceBatch | str) -> bytes:
        text = encoded.primary_sequence() if isinstance(encoded, SequenceBatch) else encoded
        return text.lower().encode()


def register(register_plugin):
    register_plugin("mycodec", MyCodec())
```

Build and install the wheel locally, then verify registration through the CLI:

```bash
cd mycodec
python -m build
pip install dist/mycodec-*.whl
genecli plugin list   # confirms the plugin is available
```

## Codec Plugin Walkthrough

1. Start from the sample at
   [`src/plugins/reverse_codec.py`](../src/plugins/reverse_codec.py). It defines
   a `ReverseCodec` class and registers it with the plugin system:

   ```python
   # src/plugins/reverse_codec.py
   from typing import Callable
   from genecoder.api import Codec
   from genecoder.formats import SequenceBatch

   class ReverseCodec(Codec):
       def encode(self, data: bytes, /, **kwargs: object) -> str:
           return data[::-1].decode("utf-8")

       def decode(self, encoded: SequenceBatch | str, /, **kwargs: object) -> bytes:
           text = encoded.primary_sequence() if isinstance(encoded, SequenceBatch) else encoded
           return text[::-1].encode("utf-8")

   def register(register_codec: Callable[[str, type[Codec]], None]) -> None:
       register_codec("reverse", ReverseCodec)
   ```

2. Load the plugin and encode data:

   ```bash
   python - <<'PY'
   from genecoder.plugins import load_plugins
   from genecoder.registry import codec_registry
   load_plugins()
   codec = codec_registry["reverse"]()
   print(codec.encode(b"HELIX"))
   PY
   ```

## Entry Point Groups

The callback passed to `register()` depends on the entry point group used:

- **Codecs** register under `genecoder.plugins` and call
  `register_codec(name, CodecClass)`.
- **FEC modules** register under `genecoder.fec` and call
  `register_fec(name, FECClass)`.
- **Simulators** register under `genecoder.simulators` and call
  `register_simulator(name, SimulatorInstance)`.
- **Visualizers** register under `genecoder.visualizers` and call
  `register_visualizer(name, VisualizerClass)`.

See the packages in [`plugins-examples`](../plugins-examples/) for working
implementations of each entry point group.

## Simulator Plugin Requirements

Channel plugins are adapters around
[``genecoder.api.Simulator``](api_reference.md#genecoder.api.Simulator). The
base class requires a ``simulate(sequence: str | SequenceBatch) -> SequenceBatch``
method that returns the mutated DNA sequence(s) for the downstream pipeline.
Implementations may override ``with_profile(profile: str)`` to support external
error profiles; the default implementation raises ``NotImplementedError`` so
simulators that expose profile selection must supply their own version.

Simulators are discovered from the ``genecoder.simulators`` entry-point group
and should use a short, descriptive slug for the entry-point key. The slug is
also passed to ``register_simulator`` and becomes the identifier used by CLI
flags such as ``genecli pipeline --channel``. A minimal configuration looks
like:

```toml
[project]
name = "my-simulator"
version = "0.1.0"
dependencies = ["genecoder"]

[project.entry-points."genecoder.simulators"]
mysim = "my_package.my_sim"
```

```python
# my_package/my_sim.py
from genecoder.api import Simulator


class Passthrough(Simulator):
    def simulate(self, sequence: str) -> str:
        return sequence


def register(register_simulator):
    register_simulator("mysim", Passthrough())
```

The package at
[`plugins-examples/example_simulator`](../plugins-examples/example_simulator/)
mirrors this layout. Its ``pyproject.toml`` defines the project metadata (name,
version and dependency on ``genecoder``) alongside the
``genecoder.simulators`` entry point, and ``example_simulator/__init__.py``
exposes the required ``register`` function.

Follow the assertions in
[`tests/test_plugin_interface_enforcement.py`](../tests/test_plugin_interface_enforcement.py)
when writing automated tests—those checks ensure every subclass provides
``simulate``—and adapt them for your simulator's own pytest suite. Once the
package is installed, confirm discovery with the CLI commands shown in
[Writing and Registering Plugins](#writing-and-registering-plugins) (for
example ``genecli plugin list``) and exercise the channel end-to-end as in the
[Simulator Plugin Walkthrough](#simulator-plugin-walkthrough).

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

## FEC Plugin Walkthrough

1. Declare the entry point in `pyproject.toml`:

   ```toml
   [project.entry-points."genecoder.fec"]
   myfec = "my_package.my_fec"
   ```

2. Implement the FEC class and register it, following the pattern in
   [`src/plugins/reverse_codec.py`](../src/plugins/reverse_codec.py):

   ```python
   # my_package/my_fec.py
   from typing import Callable, Mapping
   from genecoder.api import FEC

   class MyFEC(FEC):
       def encode(self, data: bytes, /, **kwargs: object) -> tuple[bytes, Mapping[str, object]]:
           return data, {}

       def decode(
           self, encoded: bytes, info: Mapping[str, object], /, **kwargs: object
       ) -> tuple[bytes, int]:
           return encoded, 0

   def register(register_fec: Callable[[str, type[FEC]], None]) -> None:
       register_fec("myfec", MyFEC)
   ```

3. Exercise the plugin:

   ```bash
   python - <<'PY'
   from my_package.my_fec import MyFEC
   fec = MyFEC()
   encoded, info = fec.encode(b"HELIX")
   decoded, errors = fec.decode(encoded, info)
   print(decoded, errors)
   PY
   ```

## Simulator Plugin Walkthrough

Simulator plugins model sequencing or transmission channels and use the same
registration pattern as
[`src/plugins/helix_visualizer.py`](../src/plugins/helix_visualizer.py).

```python
# src/plugins/helix_visualizer.py
from typing import Callable
from genecoder.api import Visualizer
from genecoder.app_helpers import EncodeResult, DecodeResult
from genecoder.helix_view import show_helix_ui


class HelixVisualizer(Visualizer):  # type: ignore[misc]
    def visualize(self, result: EncodeResult | DecodeResult, /, **kwargs: object) -> None:
        if isinstance(result, EncodeResult):
            show_helix_ui(result.encoded_dna, **kwargs)
        else:
            raise TypeError("HelixVisualizer supports EncodeResult only")


def register(register_visualizer: Callable[[str, type[Visualizer]], None]) -> None:
    register_visualizer("helix", HelixVisualizer)
```

1. Add an entry point in `pyproject.toml`:

   ```toml
   [project.entry-points."genecoder.simulators"]
   mysim = "my_package.my_sim"
   ```

2. Implement and register the simulator:

   ```python
   from typing import Callable
   from genecoder.api import Simulator

   class PassthroughChannel(Simulator):
       def simulate(self, sequence: str, /, **kwargs: object) -> str:
           return sequence

   def register(register_simulator: Callable[[str, Simulator], None]) -> None:
       register_simulator("mysim", PassthroughChannel())
   ```

3. Run the simulator:

   ```bash
   python - <<'PY'
   from my_package.my_sim import PassthroughChannel
   sim = PassthroughChannel()
   print(sim.simulate("ACGT"))
   PY
   ```

See [`plugins-examples/example_simulator`](../plugins-examples/example_simulator/)
for a passthrough implementation.

## Visualizer Plugins

Visualizer plugins expose custom sequence renderers via
`genecoder.visualizers`.

1. Declare an entry point:

   ```toml
   [project.entry-points."genecoder.visualizers"]
   myvis = "my_package.my_vis"
   ```

2. Provide a class implementing `visualize()` and register it:

   ```python
   from genecoder.api import Visualizer

   class MyVisualizer(Visualizer):
       def visualize(self, sequence: str, /, **kwargs):
           ...

   def register(register_visualizer):
       register_visualizer("myvis", MyVisualizer())
   ```

See [`plugins-examples/example_visualizer`](../plugins-examples/example_visualizer/)
for a minimal example.

Registered codecs are available via `genecoder.CODEC_REGISTRY` after importing
GeneCoder.

## Security Recommendations

- Install plugins only from trusted sources.
- Verify wheel checksums or signatures with
  :func:`genecoder.plugin_security.verify_signature`.
- Host registry files over HTTPS and keep them version controlled.
- Set ``GENECODER_PLUGIN_PUBLIC_KEY`` so the installer can validate
  signatures automatically.

Installing a plugin runs code from a third-party package. GeneCoder can validate
wheel signatures with
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
- `example_visualizer` – registers a visualizer with `register_visualizer("example", ExampleVisualizer)`.
- `advanced_fec` – registers LDPC helper functions under `genecoder.fec`.
- `example_package_plugin` – demonstrates a small plugin that exposes simple
  encode/decode functions through `genecoder.plugins`.

Follow these steps to try the example codec plugin:

1. From the repository root install it with:

   ```bash
   pip install ./plugins-examples/example_codec
   ```
2. Inspect `plugins-examples/example_codec/pyproject.toml` to see the
   `genecoder.plugins` entry and review the plugin module.
3. Load plugins and confirm the entry point registered:

   ```python
   from genecoder.plugins import load_plugins
   load_plugins()
   from genecoder import CODEC_REGISTRY
   print("example" in CODEC_REGISTRY)
   ```

Swap `example_codec` for `example_fec`, `example_simulator` or
`example_visualizer` to explore the other entry point groups. Install any of
these packages with `pip install ./plugins-examples/<name>` to experiment
locally.

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
address, a local `file://` URL or a plain filesystem path. When the variable is
unset no network requests are made and GeneCoder loads only plugins already
present in the current Python environment. Pass `--offline` or set
`GENECODER_OFFLINE=1` to force offline mode; the registry must then reside on
disk and any attempt to reach the network results in a clear error message.

The `install-registry` subcommand requires an explicit opt-in via
`--allow-registry`. This flag confirms you trust the registry source and want
GeneCoder to download and install the listed packages. Supply `--offline` when
all wheels and the registry file are available locally to prevent any network
access.

```bash
genecli plugin install-registry --allow-registry [--offline]
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
genecli plugin install-registry --allow-registry --offline
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

## Troubleshooting

- **Plugin not discovered** – ensure the package is installed and
  `load_plugins()` has been called.
- **Entry point missing** – check `[project.entry-points]` in `pyproject.toml`
  for typos.
- **Signature verification failed** – confirm `GENECODER_PLUGIN_PUBLIC_KEY`
  and registry checksums.

