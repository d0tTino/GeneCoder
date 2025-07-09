#!/usr/bin/env bash
# Portable script for the GeneCoder vertical slice demo
# Mirrors scripts/windows_vertical_slice.ps1
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

echo "Installing dependencies with optional extras..."
echo "Upgrading pip..."
python -m pip install --upgrade pip
poetry install --with gui,web,dnaformer --no-interaction

echo "Running CLI smoke test..."
genecoder --version
poetry run pytest -q

echo "Running bundle workflow..."
genecoder bundle run configs/vertical_slice_demo.yaml --cache-dir runs

echo "Launching the Flet GUI..."
python -m genecoder.flet_app

echo "Starting the FastAPI server..."
poetry run uvicorn web.main:app --reload
