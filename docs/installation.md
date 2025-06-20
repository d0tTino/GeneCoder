# Installation

GeneCoder requires **Python 3.10+**.

## Quick Start

Clone the repository and install the base requirements:

```bash
pip install -r requirements.txt
# Extras for optional features
pip install .[gui]  # Flet GUI
pip install .[web]  # FastAPI web interface
# For exact versions used in CI, see requirements.lock
```

## Development Setup

Install the project in editable mode so local changes are picked up immediately:

```bash
pip install -e .[gui,web]
```

## Running Tests

Unit tests use `pytest`. Install the exact versions from `requirements.lock`
before running the suite so your environment matches CI. Otherwise tests may
fail due to missing packages.

```bash
pip install -r requirements.lock
pytest -q
```

## Mamba-Based Setup

The progress report outlines a conda workflow using `mamba` to create a dedicated development environment:

```bash
mamba create -n genecoder python=3.12 flet>=0.28,<0.29 reedsolo matplotlib pytest ruff mypy
mamba activate genecoder
pip install -e .[gui,web]
pre-commit install
```
## Windows Quick Start

Install Miniforge with `winget` and create a dedicated environment using `mamba`:

```powershell
winget install conda-forge.miniforge
mamba create -n genecoder python=3.12 flet>=0.28,<0.29 reedsolo matplotlib pytest ruff mypy
mamba activate genecoder
pip install -e .[gui,web]
pre-commit install
```

Verify the installation with a quick smoke test:

```powershell
genecoder --version
pytest -q
```

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
pip install -r docs/requirements.txt
mkdocs build
```

The combined PDF will be available at `site/pdf/combined.pdf`.

