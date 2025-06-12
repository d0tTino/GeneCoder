#!/usr/bin/env bash
# Setup script for Codex CI environment
set -euo pipefail

# 1. Create/activate virtual environment
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

# 2. Install dependencies and pre-commit
pip install -r requirements.lock
pip install pre-commit

# 3. Install the pre-commit hook
pre-commit install

# 4. Determine BASE_SHA and check if only comments changed
if git rev-parse --verify origin/main >/dev/null 2>&1; then
    BASE_SHA=$(git merge-base origin/main HEAD)
else
    BASE_SHA=$(git rev-list --max-parents=0 HEAD)
fi
export BASE_SHA
only_comments=$(BASE_SHA="$BASE_SHA" python scripts/only_comments_changed.py | awk -F= '/only_comments/{print $2}')

# 5. Run lint and tests if not comment-only change
if [ "$only_comments" != "true" ]; then
    files=$(git diff --name-only "$BASE_SHA")
    if [ -n "$files" ]; then
        pre-commit run --files $files
    fi
    pytest -q
else
    echo "Only documentation or comment changes detected. Skipping pre-commit and tests."
fi
