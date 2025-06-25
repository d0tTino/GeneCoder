"""Simple security utilities for optional CLI encryption and checksums."""


from __future__ import annotations

import hashlib
import os
from typing import Optional


_AES_HEADER = b"AESGCM1"

_DEFAULT_KEY = b"GeneCoder"


def _xor_cipher(data: bytes, key: bytes) -> bytes:
    """Return ``data`` XORed with ``key``."""
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def encrypt_data(data: bytes, key: Optional[bytes] = None) -> bytes:
    """Encrypt ``data`` using AES-GCM with a random nonce."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = key or _DEFAULT_KEY
    aes_key = hashlib.sha256(key).digest()
    nonce = os.urandom(12)
    enc = bytes(AESGCM(aes_key).encrypt(nonce, data, None))
    return _AES_HEADER + nonce + enc



def decrypt_data(data: bytes, key: Optional[bytes] = None) -> bytes:
    """Decrypt data produced by :func:`encrypt_data` or legacy XOR."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = key or _DEFAULT_KEY
    if data.startswith(_AES_HEADER):
        aes_key = hashlib.sha256(key).digest()
        nonce = data[len(_AES_HEADER) : len(_AES_HEADER) + 12]
        ciphertext = data[len(_AES_HEADER) + 12 :]
        return bytes(AESGCM(aes_key).decrypt(nonce, ciphertext, None))

    return _xor_cipher(data, key)


def compute_checksum(data: bytes) -> str:
    """Return a hexadecimal SHA256 checksum for ``data``."""
    return hashlib.sha256(data).hexdigest()
