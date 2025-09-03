import pytest

import genecoder.plugin_checks as pc
from genecoder.security import compute_checksum


def test_verify_package_success():
    data = b"DATA"
    checksum = compute_checksum(data)
    assert pc.verify_package(data, checksum=checksum) == checksum


def test_verify_package_checksum_mismatch():
    data = b"DATA"
    wrong = compute_checksum(b"OTHER")
    with pytest.raises(ValueError, match="Checksum mismatch"):
        pc.verify_package(data, checksum=wrong)


def test_decode_signature_invalid():
    with pytest.raises(ValueError, match="Invalid signature"):
        pc.decode_signature("not_base64")


def test_verify_package_signature_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_compute(
        data: bytes,
        *,
        signature: bytes | None = None,
        public_key: bytes | None = None,
        padding_scheme: str = "pkcs1",
    ) -> str:
        raise ValueError("bad sig")

    monkeypatch.setattr(pc, "compute_checksum", fake_compute)
    with pytest.raises(ValueError, match="bad sig"):
        pc.verify_package(b"DATA", signature=b"sig", public_key=b"PUB")


def test_verify_package_rsa_pss() -> None:
    pytest.importorskip("cryptography.hazmat.primitives.asymmetric")
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    data = b"SIGNED"
    signature = key.sign(
        data,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )

    checksum = compute_checksum(
        data, signature=signature, public_key=pub, padding_scheme="pss"
    )
    assert (
        pc.verify_package(
            data, signature=signature, public_key=pub, padding_scheme="pss"
        )
        == checksum
    )
