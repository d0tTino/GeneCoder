#!/usr/bin/env bash
# Build desktop packages for GeneCoder using PyInstaller.
# Usage: package_desktop.sh <version>
# On macOS this creates a DMG. On Windows it creates an MSIX package.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION="${1:-0.0.0}"
DIST_DIR="$REPO_ROOT/dist"

cd "$REPO_ROOT"
mkdir -p "$DIST_DIR"

pyinstaller --noconfirm src/genecoder/flet_app.py --name GeneCoder

if [[ "$OSTYPE" == "darwin"* ]]; then
    hdiutil create "${DIST_DIR}/GeneCoder-${VERSION}.dmg" \
        -fs HFS+ -srcfolder "dist/GeneCoder.app"
elif [[ "$OSTYPE" == "msys"* || "$OSTYPE" == "cygwin"* || "$OS" == "Windows_NT" ]]; then
    pyinstaller msix --name GeneCoder --version "$VERSION" GeneCoder.spec
    mv GeneCoder.msix "${DIST_DIR}/GeneCoder-${VERSION}.msix"
fi
