#!/usr/bin/env bash
# Scaffold a minimal GeneCoder plugin project.

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $(basename "$0") <project-name>" >&2
    exit 1
fi

PROJECT=$1
MODULE=${PROJECT//-/_}

mkdir -p "$PROJECT/$MODULE"

cat > "$PROJECT/pyproject.toml" <<PY
[project]
name = "$PROJECT"
version = "0.1.0"
description = "GeneCoder plugin"
readme = "README.md"
requires-python = ">=3.9"

[project.entry-points."genecoder.plugins"]
$PROJECT = "$MODULE.plugin:register"

[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"
PY

cat > "$PROJECT/$MODULE/plugin.py" <<PY
"""$PROJECT plugin."""

def register(register_plugin):
    """Register the plugin with GeneCoder."""

    def encode(data: bytes) -> str:
        """Encode bytes to text."""
        raise NotImplementedError

    def decode(text: str) -> bytes:
        """Decode text back to bytes."""
        raise NotImplementedError

    register_plugin("$PROJECT", encode, decode)
PY

cat > "$PROJECT/README.md" <<'PY'
# GeneCoder Plugin

After implementing your plugin, build and sign a wheel:

```bash
python -m build
openssl genpkey -algorithm RSA -out private.pem -pkeyopt rsa_keygen_bits:2048
openssl rsa -in private.pem -pubout -out public.pem
openssl dgst -sha256 -sign private.pem -binary dist/*.whl | base64 > signature.txt
```

Distribute `public.pem` alongside your signed wheel so users can verify it.
PY

echo "Plugin scaffold created in $PROJECT"

