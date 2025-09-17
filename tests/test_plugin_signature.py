import hashlib

import pytest

pytest.importorskip("cryptography.hazmat.primitives.asymmetric")
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from genecoder.plugin_security import verify_signature


def _generate_keypair():
    """Return a freshly generated RSA key pair."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_bytes = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return key, public_bytes


def test_verify_signature_pkcs1_valid():
    key, public_bytes = _generate_keypair()
    data = b"signed data"
    signature = key.sign(data, padding.PKCS1v15(), hashes.SHA256())

    digest = verify_signature(data, signature, public_bytes)
    assert digest == hashlib.sha256(data).hexdigest()


def test_verify_signature_pkcs1_invalid_signature():
    key, public_bytes = _generate_keypair()
    data = b"signed data"
    signature = key.sign(data, padding.PKCS1v15(), hashes.SHA256())
    bad_signature = b"\x00" + signature[1:]

    with pytest.raises(ValueError, match="Invalid signature"):
        verify_signature(data, bad_signature, public_bytes)


def test_verify_signature_pss_valid():
    key, public_bytes = _generate_keypair()
    data = b"signed data"
    signature = key.sign(
        data,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )

    digest = verify_signature(data, signature, public_bytes, padding_scheme="pss")
    assert digest == hashlib.sha256(data).hexdigest()


def test_verify_signature_pss_mismatch():
    key, public_bytes = _generate_keypair()
    data = b"signed data"
    signature = key.sign(data, padding.PKCS1v15(), hashes.SHA256())

    with pytest.raises(ValueError, match="Invalid signature"):
        verify_signature(data, signature, public_bytes, padding_scheme="pss")


def test_verify_signature_checksum_mismatch():
    key, public_bytes = _generate_keypair()
    data = b"signed data"
    signature = key.sign(data, padding.PKCS1v15(), hashes.SHA256())
    bad_checksum = "0" * 64

    with pytest.raises(ValueError, match="Checksum mismatch"):
        verify_signature(
            data,
            signature,
            public_bytes,
            expected_checksum=bad_checksum,
        )

