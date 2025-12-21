"""Utilities for verifying plugin packages."""

from __future__ import annotations

import base64
import importlib.util


def _has_cryptography() -> bool:
    try:
        return importlib.util.find_spec("cryptography.exceptions") is not None
    except (ValueError, ModuleNotFoundError):
        return False


if _has_cryptography():
    from cryptography.exceptions import InvalidSignature
else:  # pragma: no cover - exercised when cryptography is unavailable
    class InvalidSignature(Exception):
        """Fallback signature error when cryptography is unavailable."""

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
    data: bytes,
    signature: bytes,
    public_key: bytes,
    *,
    padding_scheme: str = "pkcs1",
    expected_checksum: str | None = None,
) -> str:
    """Return the SHA256 digest for ``data`` after signature validation.

    Parameters are forwarded to :func:`genecoder.security.compute_checksum`.
    ``InvalidSignature`` from the underlying cryptography library is converted
    into ``ValueError`` so callers can handle failures uniformly. When
    ``expected_checksum`` is provided the value is normalised via
    :func:`decode_checksum` and compared against the computed digest. A mismatch
    raises ``ValueError`` with a clear error message. Callers can persist the
    returned digest in registry metadata for subsequent verification.
    """

    try:
        digest = _compute_checksum(
            data,
            signature=signature,
            public_key=public_key,
            padding_scheme=padding_scheme,
        )
    except InvalidSignature as exc:  # pragma: no cover - exercised in tests
        raise ValueError("Invalid signature") from exc

    if expected_checksum is not None:
        try:
            expected = decode_checksum(expected_checksum)
        except ValueError as exc:  # pragma: no cover - invalid checksum encoding
            raise ValueError("Invalid checksum") from exc
        if digest != expected:
            raise ValueError("Checksum mismatch")

    return digest
