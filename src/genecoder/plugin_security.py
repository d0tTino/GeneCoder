from __future__ import annotations

"""Utilities for verifying plugin packages."""

from .security import compute_checksum as _compute_checksum


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
