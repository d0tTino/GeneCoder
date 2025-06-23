#!/usr/bin/env bash
# Export Poetry dependencies to requirements.txt and requirements.lock
# for compatibility with tooling that expects pip-style requirements files.
# Usage: scripts/export_requirements.sh [extras]

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

EXTRAS=${1:-}

if [[ -n "$EXTRAS" ]]; then
    EXTRA_FLAG="--extras $EXTRAS"
else
    EXTRA_FLAG=""
fi

poetry export $EXTRA_FLAG --format requirements.txt --output requirements.txt
poetry export $EXTRA_FLAG --format requirements.txt --without-hashes --output requirements.lock
