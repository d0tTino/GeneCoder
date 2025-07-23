#!/usr/bin/env bash
# Install optional dependencies used by tests
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

echo "Installing GUI, web and development extras..."
poetry install --with gui,web,dev --no-interaction
