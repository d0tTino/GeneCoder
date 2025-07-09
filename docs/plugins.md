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

Plugins can be installed automatically from a remote registry using the
:func:`genecoder.plugins.install_registry_plugins` function or the
``genecoder plugin install-registry`` command. Set the environment variable
``GENECODER_PLUGIN_REGISTRY_URL`` to the URL of a YAML file listing plugin
packages and then run the installer. Example:


```bash
export GENECODER_PLUGIN_REGISTRY_URL=https://example.com/registry.yaml
```

Then install the packages with:

```bash
genecoder plugin install-registry
```

The registry file must contain:

```yaml
packages:
  - spec: genecoder-fancy-plugin>=1.0
    checksum: abcdef123456...
    signature: BASE64_SIG
  - spec: git+https://example.com/user/custom.git
    checksum: 0123456789ab...
    signature: ANOTHER_SIG
```

Set ``GENECODER_PLUGIN_PUBLIC_KEY`` to the path of the PEM encoded public key
used to verify these signatures. Registry entries without a valid ``signature``
field are ignored. Only HTTPS URLs (or ``file://`` for local testing) are
accepted. Each package is installed only if the signature verifies and the
checksum matches; installation uses ``pip install --require-hashes`` so the
downloaded file must match the expected SHA256 digest; otherwise installation
is aborted and a warning is logged. The
checksum check merely confirms that the package was not altered in transit; it
does **not** guarantee the plugin is safe. Always use registries from trusted
sources and review plugins before installing them.

## Plugin Marketplace

Set ``GENECODER_PLUGIN_CATALOG_URL`` to a JSON or YAML file describing
available plugins. Example:

```bash
export GENECODER_PLUGIN_CATALOG_URL=https://example.com/catalog.yaml
```

The file may be JSON or YAML and should follow this structure:

```yaml
plugins:
  - name: myplugin
    version: "1.0.0"
    url: myplugin==1.0.0
    description: Example plugin
    author: Example Author
    stars: 4.5
```

The URL may use HTTP(S) or point to a local file via ``file://``.

JSON uses the same keys:

```json
{
  "plugins": [
    {"name": "myplugin", "version": "1.0.0", "url": "myplugin==1.0.0", "description": "Example plugin", "author": "Example Author", "stars": 4.5}
  ]
}
```

After loading plugins, list available entries:

```bash
genecoder plugin list
```

Install a plugin from the catalog:

```bash
genecoder plugin install myplugin
```

The ``/plugin-catalog`` web page lets you search and sort available plugins by
name, description or rating. To submit feedback programmatically send a rating
to the API. Both rating endpoints require an API token supplied in the
``Authorization`` header:

```bash
curl -X POST -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"name": "myplugin", "rating": 5}' http://localhost:8000/plugins/rate
```

The response includes the updated average star count for the plugin.

Ratings can also be retrieved via ``GET /plugins/rate``:

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  'http://localhost:8000/plugins/rate?name=myplugin'
```

For convenience the CLI exposes a ``rate`` command:

```bash
genecoder plugin rate myplugin 5 --server https://localhost:8000
```

Always verify that catalog entries originate from reputable sources or trusted
registries. A matching checksum only proves the downloaded file has not been
corrupted or tampered with; it does not guarantee that the plugin's code is
safe to execute. Review the plugin code when possible and install only from
maintained or well-known repositories.

## Third-Party Plugin Risks and Verification

GeneCoder automatically imports any packages that expose the appropriate entry
points or are listed in a plugin registry. These plugins execute arbitrary
Python code with the privileges of the current user. Malicious or poorly
written plugins could therefore compromise your system or corrupt data.

GeneCoder itself does not verify the authenticity of third-party packages. When
using a registry or catalog, ensure the listed sources are trustworthy and, if
possible, manually inspect the plugin code or compare checksums before
installation.

## Signed Plugin Packages

For higher assurance you may sign plugin distributions with an RSA or ECDSA
private key and publish the detached signature alongside the package. The
catalog or registry entry should include the base64 encoded signature under the
``signature`` field. Set the ``GENECODER_PLUGIN_PUBLIC_KEY`` environment
variable to the path of the corresponding PEM encoded public key. During
installation GeneCoder verifies the signature before falling back to the regular
checksum check. A failed signature verification aborts the install and logs a
warning.

Signed packages help detect tampering, but they do not make untrusted code safe.
Always audit plugins and obtain public keys from verified sources.

## Running the Plugin Catalog Service

The web server exposes a small REST API for hosting plugin metadata. Set
``GENECODER_CATALOG_PATH`` to the location of a JSON file before starting the
FastAPI application:

```bash
export GENECODER_CATALOG_PATH=/tmp/catalog.json
uvicorn web.main:app
```

Upload a plugin entry with a POST request including the name, version, checksum
and optional signature:

```bash
curl -X POST -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"name": "demo", "version": "1.0", "checksum": "abc", "signature": "sig"}' \
     http://localhost:8000/catalog/plugins
```

List registered entries via ``GET /catalog/plugins``.

## Submitting to the Marketplace

Signed plugin packages can be shared publicly by submitting them to the GeneCoder marketplace. After building a wheel and generating the detached signature, visit the marketplace dashboard and upload both files. The system verifies the signature and runs automated checks before listing the plugin in the public catalog.
