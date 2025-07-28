#!/usr/bin/env bash
# Build and run the GeneCoder Docker image for offline development
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

IMAGE_NAME="genecoder-dev"

echo "Building $IMAGE_NAME from Dockerfile..."
docker build -t "$IMAGE_NAME" .

echo "Launching $IMAGE_NAME container..."
docker run --rm -it --network none \
  -v "$REPO_ROOT":/workspace \
  -e GENECODER_PLUGIN_REGISTRY_URL= \
  -e GENECODER_PROFILE_DIR= \
  "$IMAGE_NAME" bash
