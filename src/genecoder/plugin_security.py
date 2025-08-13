"""Utilities for verifying plugin packages."""

from __future__ import annotations

import base64

from .security import compute_checksum as _compute_checksum


_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


def decode_checksum(checksum: str) -> str:
    """Return a hex digest for *checksum* encoded as hex or Base64.

    The input may either be a hexadecimal string or a Base64 encoded digest.
    The returned value is always a lowercase hexadecimal string.
    ``ValueError`` is raised if *checksum* cannot be decoded.
    """

    text = checksum.strip()
    if len(text) % 2 == 0 and all(ch in _HEX_DIGITS for ch in text):
        return text.lower()
    try:
        raw = base64.b64decode(text, validate=True)
    except Exception as exc:  # pragma: no cover - decoding failure
        raise ValueError("Invalid checksum encoding") from exc
    return raw.hex()


def compute_checksum(
    data: bytes,
    *,
    signature: bytes | None = None,
    public_key: bytes | None = None,
    padding_scheme: str = "pkcs1",
) -> str:
    """Return the SHA256 checksum of *data*."""
    return _compute_checksum(
        data,
        signature=signature,
        public_key=public_key,
        padding_scheme=padding_scheme,
    )


def verify_signature(
    data: bytes, signature: bytes, public_key: bytes, *, padding_scheme: str = "pkcs1"
) -> None:
    """Raise if *signature* does not verify *data* with *public_key*."""
    _compute_checksum(
        data,
        signature=signature,
        public_key=public_key,
        padding_scheme=padding_scheme,
    )
