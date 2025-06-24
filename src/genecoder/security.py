"""Simple security utilities for optional CLI encryption and checksums."""

from __future__ import annotations

import hashlib
from typing import Optional

_DEFAULT_KEY = b"GeneCoder"


def encrypt_data(data: bytes, key: Optional[bytes] = None) -> bytes:
    """XOR-encrypt ``data`` using ``key`` (defaults to a static value)."""
    key = key or _DEFAULT_KEY
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def decrypt_data(data: bytes, key: Optional[bytes] = None) -> bytes:
    """Decrypt data previously encrypted with :func:`encrypt_data`."""
    return encrypt_data(data, key)


def compute_checksum(data: bytes) -> str:
    """Return a hexadecimal SHA256 checksum for ``data``."""
    return hashlib.sha256(data).hexdigest()
