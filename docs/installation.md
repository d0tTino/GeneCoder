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
| `framed`      | FrameD C++ backend                              |
| `dnaformer`   | DNAformer AI codec                              |
| `deepdna`     | DeepDNA FEC plugin                              |

Install every group required for development and testing with:

```bash
poetry install --with gui,web,dev \
  --extras ldpc --extras fountain --extras bch \
  --extras raptorq --extras framed --extras dnaformer \
  --extras deepdna --no-interaction
```

These packages are quite large (Flet and the various FEC backends in
particular). Installing all of them uses roughly **2&nbsp;GB** of disk space and
takes about **10&nbsp;minutes** on a typical broadband connection.

## Editable install with pip

If you prefer `pip`, ensure you are using **Python 3.11+** and install the
repository in editable mode so changes take effect immediately:

```bash
python -m pip install -e .[gui,web]
```
This command installs the optional GUI and web dependencies in editable mode.

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
can still build the image and run the tests manually:

```bash
docker build -t genecoder .
docker run --rm -e SKIP_PACKAGING_TESTS=1 genecoder poetry run pytest -q
```
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

## FrameD FEC Backend

The optional FrameD plugin wraps optimized C++ kernels using CFFI to provide additional
[FEC](glossary.md#forward-error-correction-fec) methods.
Install it using the ``framed`` extras:

```bash
poetry install --extras framed --no-interaction
```



The `framed` FEC method becomes available automatically after
installation.

## Licenses for Optional Extras

GeneCoder itself and all core functionality use permissive licenses. Some
optional extras come with additional requirements:

* **FrameD** &ndash; [LGPLv3](https://www.gnu.org/licenses/lgpl-3.0.html)
* **DeepDNA** &ndash; [MIT](https://opensource.org/license/mit/)

These components are only needed when installing the corresponding extras.

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

