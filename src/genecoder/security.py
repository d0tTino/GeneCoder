"""Simple security utilities for optional CLI encryption and checksums."""


from __future__ import annotations

import hashlib
import os


_AES_HEADER = b"AESGCM1"


def _xor_cipher(data: bytes, key: bytes) -> bytes:
    """Return ``data`` XORed with ``key``."""
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def encrypt_data(data: bytes, key: bytes) -> bytes:
    """Encrypt ``data`` using AES-GCM with a random nonce."""

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aes_key = hashlib.sha256(key).digest()
    nonce = os.urandom(12)
    enc: bytes = AESGCM(aes_key).encrypt(nonce, data, None)


    return _AES_HEADER + nonce + enc

def decrypt_data(data: bytes, key: bytes) -> bytes:
    """Decrypt data produced by :func:`encrypt_data` or legacy XOR."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if data.startswith(_AES_HEADER):
        aes_key = hashlib.sha256(key).digest()
        nonce = data[len(_AES_HEADER) : len(_AES_HEADER) + 12]
        ciphertext = data[len(_AES_HEADER) + 12 :]
        dec: bytes = AESGCM(aes_key).decrypt(nonce, ciphertext, None)
        return dec

    return _xor_cipher(data, key)


def compute_checksum(
    data: bytes,
    *,
    signature: bytes | None = None,
    public_key: bytes | None = None,
) -> str:
    """Return a hexadecimal SHA256 checksum for ``data``.

    If ``signature`` and ``public_key`` are provided, verify that the signature
    matches ``data`` using RSA or ECDSA with a SHA256 hash. ``InvalidSignature``
    or ``ValueError`` is raised on failure.
    """

    digest = hashlib.sha256(data).hexdigest()

    if signature is not None:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, ec, rsa

        if public_key is None:
            raise ValueError("public_key required when verifying a signature")

        key = serialization.load_pem_public_key(public_key)
        if isinstance(key, rsa.RSAPublicKey):
            key.verify(signature, data, padding.PKCS1v15(), hashes.SHA256())
        elif isinstance(key, ec.EllipticCurvePublicKey):
            key.verify(signature, data, ec.ECDSA(hashes.SHA256()))
        else:  # pragma: no cover - unsupported key type
            raise InvalidSignature("Unsupported key type")

    return digest
