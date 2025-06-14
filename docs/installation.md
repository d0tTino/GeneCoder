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

Install [Miniforge](https://github.com/conda-forge/miniforge#miniforge3). Then create and activate a dedicated environment:

```bash
mamba create -n genecoder python=3.10
conda activate genecoder
```

Finally, install the dependencies and the project in editable mode:

```bash
pip install -r requirements.txt
pip install -e .
```

