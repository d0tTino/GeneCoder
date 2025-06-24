# Installation

GeneCoder requires **Python 3.10+**.

## Quick Start

Clone the repository and install the base requirements using
[Poetry](https://python-poetry.org/):

```bash
poetry install --no-interaction
```
Poetry manages all dependencies. `pyproject.toml` and `poetry.lock` are the single source of truth. Use `scripts/export_requirements.sh` if you need `requirements.txt` files.


Install optional extras with the `--with` flag:

```bash
poetry install --with gui,web --no-interaction
```

## Editable install with pip

If you prefer `pip`, ensure you are using **Python 3.10+** and install the
repository in editable mode so changes take effect immediately:

```bash
python -m pip install -e .[gui,web]
```

## Development Setup

Install the project in editable mode so local changes are picked up immediately:

```bash
poetry install --with gui,web,dev --no-interaction
```

## Running Tests

Run the tests inside the Poetry environment:

```bash
poetry run pytest -q
```

## Docker Dev Container

The repository ships with a Visual Studio Code Dev Container configuration. You
can still build the image and run the tests manually:

```bash
docker build -t genecoder .
docker run --rm -e SKIP_PACKAGING_TESTS=1 genecoder poetry run pytest -q
```

To hack on GeneCoder in the same environment, install the **Dev Containers**
extension in VS Code and select **Reopen in Container** when prompted. The
container extends the project `Dockerfile` and includes Node and other helpful
development tools.

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
genecoder --version
poetry run pytest -q
```

## DNAformer Plugin

Install the optional DNAformer model separately. The plugin requires
`dnaformer` and `torch` which are not installed with the base
dependencies:

```bash
pip install dnaformer torch
```

Once installed, GeneCoder will automatically register the codec when
imported.

## FrameD FEC Backend

The optional FrameD plugin wraps optimized C++ kernels using CFFI.
Install the package from PyPI before using the backend:

```bash
pip install FrameD
```

The `framed` FEC method becomes available automatically after
installation.

## Configuring the OpenAI API Key

The OpenAI testing agent requires an API key. Set the `OPENAI_API_KEY`
environment variable before running the agent tests.

Add the key to a `.env` file at the project root:

```bash
OPENAI_API_KEY=sk-yourkey
```

Load the file before running tests, for example with:

```bash
set -a && source .env && set +a
```

Or export the variable directly:

```bash
export OPENAI_API_KEY=sk-yourkey
```

## Building the Documentation

Install the documentation dependencies and generate the static site:

```bash
poetry run pip install -r docs/requirements.txt
poetry run mkdocs build
```

The combined PDF will be available at `site/pdf/combined.pdf`.

