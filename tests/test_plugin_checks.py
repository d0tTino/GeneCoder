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
    def fake_compute(data: bytes, *, signature: bytes | None = None, public_key: bytes | None = None) -> str:
        raise ValueError("bad sig")

    monkeypatch.setattr(pc, "compute_checksum", fake_compute)
    with pytest.raises(ValueError, match="bad sig"):
        pc.verify_package(b"DATA", signature=b"sig", public_key=b"PUB")
