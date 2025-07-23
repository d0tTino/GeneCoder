#!/usr/bin/env bash
# Install all extras needed for the full test suite
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

echo "Installing base package..."
pip install -e .

EXTRAS=(ldpc fountain bch raptorq)
for extra in "${EXTRAS[@]}"; do
    echo "Installing extras: $extra"
    if pip install -e ".[$extra]"; then
        echo "Installed $extra"
    else
        echo "Skipping $extra (dependency not available)"
    fi
done

