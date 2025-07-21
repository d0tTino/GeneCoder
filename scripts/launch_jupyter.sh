#!/usr/bin/env bash
# Setup the GeneCoder environment and launch Jupyter
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

# Install dependencies and Jupyter if needed
poetry install --no-interaction
poetry run pip install --quiet jupyterlab

# Launch Jupyter Lab in the notebooks directory
poetry run jupyter lab notebooks
