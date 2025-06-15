#!/usr/bin/env bash
# Start the OpenAI testing agent demo and GeneCoder Flet GUI.
# Requires Node.js and Python dependencies to be installed.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT/openai_testing"
# Install Node dependencies if they have not been installed yet
npm install
npx playwright install --with-deps || true
npm run dev &
DEV_PID=$!

# Wait a bit for servers to start
sleep 5

cd "$REPO_ROOT"
python -m genecoder.flet_app

kill $DEV_PID
