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

Install locked dependencies and run the test suite:

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

