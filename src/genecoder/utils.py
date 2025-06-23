"""Utility helpers shared across modules."""

from __future__ import annotations

import hashlib
import os

DNA_ENCODE_MAP = {"00": "A", "01": "C", "10": "G", "11": "T"}
"""Mapping from two-bit binary strings to DNA bases (Base-4 alphabet)."""

DNA_DECODE_MAP = {v: k for k, v in DNA_ENCODE_MAP.items()}
"""Reverse mapping from DNA bases back to two-bit binary strings."""

ALPHABETS: dict[str, str] = {
    "base4": "ACGT",
    "base5": "ACGTN",
    "base6": "ACGTRY",
}
"""Supported nucleotide alphabets for encoding."""


def get_alphabet_maps(alphabet: str) -> tuple[dict[str, str], dict[str, str]]:
    """Return encode/decode maps for the selected alphabet."""
    if alphabet not in ALPHABETS:
        raise ValueError(f"Unknown alphabet '{alphabet}'")
    letters = ALPHABETS[alphabet]
    encode_map = {
        "00": letters[0],
        "01": letters[1],
        "10": letters[2],
        "11": letters[3],
    }
    decode_map = {v: k for k, v in encode_map.items()}
    return encode_map, decode_map


def get_max_homopolymer_length(dna_sequence: str) -> int:
    """Calculates the length of the longest homopolymer in a DNA sequence.

    Args:
        dna_sequence: The DNA sequence string (e.g., "AAATTCGGGG").

    Returns:
        The length of the longest homopolymer. Returns 0 for an empty sequence.
    """
    if not dna_sequence:
        return 0
    dna_sequence = dna_sequence.upper()

    max_len = 0
    current_len = 0
    if len(dna_sequence) > 0:
        current_char = dna_sequence[0]
        current_len = 1
        max_len = 1

    for i in range(1, len(dna_sequence)):
        if dna_sequence[i] == current_char:
            current_len += 1
        else:
            current_char = dna_sequence[i]
            current_len = 1

        if current_len > max_len:
            max_len = current_len

    return max_len if dna_sequence else 0


def check_homopolymer_length(dna_sequence: str, max_len: int) -> bool:
    """Checks if any homopolymer in the DNA sequence exceeds a maximum length."""
    return get_max_homopolymer_length(dna_sequence) > max_len


def encrypt_bytes(data: bytes, key: bytes) -> bytes:
    """Encrypt ``data`` with AES-256 CBC using ``key``.

    The 16-byte IV is prepended to the returned ciphertext.
    """
    if len(key) != 32:
        raise ValueError("AES-256 key must be 32 bytes")
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7

    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    padder = PKCS7(128).padder()
    padded = padder.update(data) + padder.finalize()
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return iv + bytes(ciphertext)


def decrypt_bytes(data: bytes, key: bytes) -> bytes:
    """Decrypt AES-256 CBC ``data`` using ``key``."""
    if len(key) != 32:
        raise ValueError("AES-256 key must be 32 bytes")
    if len(data) < 16:
        raise ValueError("Ciphertext too short")
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7

    iv, ciphertext = data[:16], data[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    return bytes(unpadder.update(padded) + unpadder.finalize())


def sha256_checksum(data: bytes) -> str:
    """Return the SHA-256 checksum of ``data`` as a hex string."""
    return hashlib.sha256(data).hexdigest()


def parse_encryption_key(key_str: str) -> bytes:
    """Return the binary key from a hex string.

    Raises ``ValueError`` if the key is not hex encoded or not 32 bytes.
    """
    try:
        key_bytes = bytes.fromhex(key_str)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError("--encryption-key must be hex-encoded") from exc
    if len(key_bytes) != 32:
        raise ValueError("--encryption-key must be 32 bytes (64 hex characters).")
    return key_bytes


__all__ = [
    "ALPHABETS",
    "check_homopolymer_length",
    "decrypt_bytes",
    "encrypt_bytes",
    "get_alphabet_maps",
    "get_max_homopolymer_length",
    "parse_encryption_key",
    "sha256_checksum",
]

