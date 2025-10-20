# Installation

GeneCoder requires **Python 3.11+**.

## Quick Start

Clone the repository and install the base requirements using
[Poetry](https://python-poetry.org/):

```bash
poetry install --no-interaction
```
Poetry manages all dependencies. `pyproject.toml` and `poetry.lock` are the single source of truth. Use `scripts/export_requirements.sh` if you need `requirements.txt` files.

GUI and web functionality are not installed by default. Add them with
`poetry install --with gui --with web` when needed.



## Optional Extras

GeneCoder exposes several optional extras to keep the default installation
lightweight. Each extra installs only the dependencies needed for specific
features, such as additional codecs or development tools.

GUI and web functionality are optional. Install their dependencies with Poetry's
`--with` flag:

```bash
poetry install --with gui,web,dnaformer --no-interaction
```
The `gui` group installs Flet, Matplotlib and `flet-webview` while the `web`
group pulls in FastAPI, Uvicorn (with the `standard` extras) and HTTPX.

## Extras Required for the Full Test Suite

Install all extras needed to exercise the complete test suite. This table lists
the optional groups and what they provide:

| Extras        | Provides                                        |
|---------------|-------------------------------------------------|
| `gui`         | Flet GUI and helix viewer dependencies          |
| `web`         | FastAPI server and HTTPX client                 |
| `dev`         | Pytest, Ruff, MyPy, types-PyYAML and Playwright tools |
| `ldpc`        | Low-density parity-check codes                  |
| `fountain`    | Fountain code support                           |
| `bch`         | BCH error-correcting codes                      |
| `raptorq`     | RaptorQ FEC algorithms                          |
| `dnaformer`   | DNAformer AI codec                              |
| `deepdna`     | DeepDNA FEC plugin                              |

Install every group required for development and testing with:

```bash
poetry install --with gui,web,dev \
  --extras ldpc --extras fountain --extras bch \
  --extras raptorq --extras dnaformer \
  --extras deepdna --no-interaction
```

These packages are quite large (Flet and the various FEC backends in
particular). Installing all of them uses roughly **2&nbsp;GB** of disk space and
takes about **10&nbsp;minutes** on a typical broadband connection.

> **FrameD availability:** FrameD support has been retired and the wrapper is no
> longer distributed. The upstream LGPL package is unmaintained on modern
> platforms, so GeneCoder now recommends the LDPC, Fountain or RaptorQ extras
> when advanced forward-error-correction is required.

## Editable install with pip

If you prefer `pip`, ensure you are using **Python 3.11+** and install the
repository in editable mode so changes take effect immediately:

```bash
python -m pip install -e .[gui,web,dev]
```
This command installs the optional GUI, web, and development dependencies in
editable mode. The `dev` group pulls in stub packages like `types-PyYAML` so
`mypy` runs without additional steps. Make sure this stub package is
installed whenever you run the type checker.

## Development Setup

Install the project in editable mode so local changes are picked up immediately:

```bash
poetry install --with gui,web,dev --no-interaction
```
This also installs the `types-PyYAML` stub package required by MyPy for YAML type checking.

Contributors can alternatively open the repository in the provided
**devcontainer** for a fully preconfigured environment.

## Running Tests

Install the development dependencies before running the tests:

```bash
poetry install --with dev --no-interaction
poetry run pytest -q
```

## Docker Dev Container

The repository ships with a Visual Studio Code Dev Container configuration. You
can still build the image manually using the included `Dockerfile`:

```bash
docker build -t genecoder .
```

For a quick offline setup run the helper script which mounts the current
repository into a container based on that image and disables networking:

```bash
./scripts/docker_dev.sh
```

Inside the container you can run commands like `poetry run pytest -q` without
network access.
## Using the Dev Container

Run `devcontainer open` from the repository root to build and launch the configured environment. Alternatively, install the **Dev Containers** extension in VS Code and select **Reopen in Container** when prompted. The container extends the project `Dockerfile` and includes Node and other helpful development tools.



## Mamba-Based Setup

The progress report outlines a conda workflow using `mamba` to create a dedicated development environment:

```bash
mamba create -n genecoder python=3.12 flet>=0.28,<0.29 reedsolo matplotlib pytest ruff mypy
mamba activate genecoder
poetry install --with gui,web,dev --no-interaction
pre-commit install
```
## Windows Quick Start

Install Miniforge with `winget` and create a dedicated environment using `mamba`:

```powershell
winget install conda-forge.miniforge
mamba create -n genecoder python=3.12 flet>=0.28,<0.29 reedsolo matplotlib pytest ruff mypy
mamba activate genecoder
poetry install --with gui,web,dev --no-interaction
pre-commit install
```

Verify the installation with a quick smoke test:

```powershell
genecli --version
poetry run pytest -q
```

## DNAformer Plugin

Install the optional DNAformer model with Poetry's extras support:

```bash
poetry install --extras dnaformer --no-interaction
```

Once installed, GeneCoder will automatically register the codec when
imported.

## DeepDNA Plugin

Install the optional DeepDNA model with Poetry's extras support:

```bash
poetry install --extras deepdna --no-interaction
```

The codec registers itself automatically when imported.

## Licenses for Optional Extras

GeneCoder itself and all core functionality use permissive licenses. Some
optional extras come with additional requirements:

* **DeepDNA** &ndash; [MIT](https://opensource.org/license/mit/)

FrameD is no longer supported by GeneCoder because the upstream project is
unmaintained. LDPC, Fountain and RaptorQ extras provide advanced
forward-error-correction under permissive licenses. Other components are only
needed when installing the corresponding extras.

## Custom Temporary Directory

GeneCoder writes short-lived files during testing and simulation. Set the
`GENECODER_TMP` environment variable to change where these temporary files
are created. By default the system's standard location is used. The
resolved directory can be obtained with ``genecoder.utils.get_temp_dir()``.

## Building the Documentation

Install the documentation dependencies and generate the static site:

```bash
poetry run pip install -r docs/requirements.txt
poetry run mkdocs build
```

The combined PDF will be available at `site/pdf/combined.pdf`.

## Offline Setup

GeneCoder works without network access by default. Only plugins already
installed in the current environment are loaded and no external profiles are
fetched. To explicitly disable remote lookups set these environment variables to
empty strings:

```bash
export GENECODER_PLUGIN_REGISTRY_URL=
export GENECODER_PROFILE_DIR=
```

Setting `GENECODER_PROFILE_DIR` avoids attempts to download simulator profiles
while `GENECODER_PLUGIN_REGISTRY_URL` ensures plugins are discovered solely from
local packages. The CLI and GUI behave the same way when these variables are
unset or empty, making this the recommended configuration for air‑gapped
systems.

## Installing Registry Plugins Offline

Use the :func:`genecoder.plugin_manager.install_registry_plugins` helper with
``offline=True`` to install plugins from a local registry without network
access. Supplying a remote URL in this mode raises ``RuntimeError`` to prevent
accidental downloads.

```python
from genecoder import plugin_manager as plugins

plugins.install_registry_plugins("/path/to/registry.yaml", offline=True)
```

This flag is also honored when the ``GENECODER_OFFLINE`` environment variable
is set.

## Plugin Verification

Plugin registries record a `checksum` or `signature` for every wheel. The
installer computes the SHA256 digest of each download and compares it against
this information before proceeding. Provide the verification key via the
`GENECODER_PLUGIN_PUBLIC_KEY` environment variable so signatures are checked
automatically. Installation fails if the digest or signature does not match.
See [Plugin Security](plugins.md#plugin-security) for more details.

## Configuring Optional Simulators

External simulators accept additional flags through environment variables. Set
`GENECODER_D2SIM_OPTIONS`, `GENECODER_DNARSIM_OPTIONS` or
`GENECODER_SQUIGULATOR_OPTIONS` to pass options to the respective tool. Use
`GENECODER_SIM_SEED` to make runs reproducible.

