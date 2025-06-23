import hashlib
from genecoder.utils import encrypt_bytes, decrypt_bytes, sha256_checksum


def test_encrypt_decrypt_roundtrip() -> None:
    key = bytes.fromhex('00' * 32)
    data = b'secret message'
    encrypted = encrypt_bytes(data, key)
    assert encrypted != data
    decrypted = decrypt_bytes(encrypted, key)
    assert decrypted == data


def test_sha256_checksum() -> None:
    data = b'abc'
    assert sha256_checksum(data) == hashlib.sha256(data).hexdigest()
