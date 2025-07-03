"""Simple security utilities for optional CLI encryption and checksums."""


from __future__ import annotations

import hashlib
import os
from typing import Optional


_AES_HEADER = b"AESGCM1"

_DEFAULT_KEY = b"GeneCoder"


def encrypt_data(data: bytes, key: Optional[bytes] = None) -> bytes:
    """Return ``data`` encrypted using AES-GCM with a random nonce."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = key or _DEFAULT_KEY
    aes_key = hashlib.sha256(key).digest()
    nonce = os.urandom(12)
    enc: bytes = AESGCM(aes_key).encrypt(nonce, data, None)


    return _AES_HEADER + nonce + enc


def decrypt_data(data: bytes, key: Optional[bytes] = None) -> bytes:
    """Decrypt bytes produced by :func:`encrypt_data`.

    Parameters
    ----------
    data:
        Bytes previously returned by :func:`encrypt_data`.
    key:
        Optional secret key used during encryption. If omitted, a built-in
        default is used.

    Raises
    ------
    ValueError
        If ``data`` does not appear to be AES encrypted.
    cryptography.exceptions.InvalidTag
        If decryption fails because the key or ciphertext is invalid.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = key or _DEFAULT_KEY
    if not data.startswith(_AES_HEADER):
        raise ValueError("Data is not AES encrypted")

    aes_key = hashlib.sha256(key).digest()
    nonce = data[len(_AES_HEADER) : len(_AES_HEADER) + 12]
    ciphertext = data[len(_AES_HEADER) + 12 :]
    dec: bytes = AESGCM(aes_key).decrypt(nonce, ciphertext, None)
    return dec


def compute_checksum(data: bytes) -> str:
    """Return a hexadecimal SHA256 checksum for ``data``."""
    return hashlib.sha256(data).hexdigest()
