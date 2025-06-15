# Installation

GeneCoder requires Python 3.10 or higher. Clone the repository and install dependencies:

```bash
pip install -r requirements.txt  # installs flet>=0.28,<0.29
# For exact versions used in CI, see requirements.lock
```

For development, install the project in editable mode. This lets you run the CLI
as `genecoder` and immediately pick up local changes:

```bash
pip install -e .
```

## Running Tests

Unit tests use `pytest`. Install the exact versions from `requirements.lock`
before running the suite so your environment matches CI. Otherwise tests may
fail due to missing packages.

```bash
pip install -r requirements.lock
pytest -q
```
## Windows Quick Start

Install Miniforge with `winget` and create a dedicated environment using `mamba`:

```powershell
winget install conda-forge.miniforge
mamba create -n genecoder python=3.12 flet reedsolo matplotlib pytest ruff mypy
mamba activate genecoder
pip install -e .
pre-commit install
```

Verify the installation with a quick smoke test:

```powershell
genecoder --version
pytest -q
```

