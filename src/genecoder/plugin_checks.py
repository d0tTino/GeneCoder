from __future__ import annotations

"""Helper utilities for validating plugin packages."""

import base64
from typing import Callable

from .security import compute_checksum

__all__ = ["decode_signature", "verify_package"]


def decode_signature(signature_b64: str) -> bytes:
    """Return raw signature bytes decoded from base64."""
    try:
        return base64.b64decode(signature_b64, validate=True)
    except Exception as exc:  # pragma: no cover - invalid base64
        raise ValueError("Invalid signature") from exc


def verify_package(
    data: bytes,
    *,
    checksum: str | None = None,
    signature: bytes | None = None,
    public_key: bytes | None = None,
    compute_fn: Callable[..., str] | None = None,
) -> str:
    """Return the SHA256 digest of ``data`` after optional verification.

    ``checksum`` is compared against the computed digest when provided.
    ``signature`` and ``public_key`` are used for signature verification when
    both are given. ``ValueError`` is raised on a checksum mismatch.
    """
    if compute_fn is None:
        compute_fn = compute_checksum
    digest = compute_fn(data, signature=signature, public_key=public_key)
    if checksum is not None and digest != checksum:
        raise ValueError("Checksum mismatch")
    return digest
