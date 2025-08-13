import base64
import pytest

from genecoder.plugin_security import compute_checksum, decode_checksum


def test_decode_checksum_hex_and_base64() -> None:
    data = b"ABC"
    digest = compute_checksum(data)
    assert decode_checksum(digest) == digest
    b64 = base64.b64encode(bytes.fromhex(digest)).decode()
    assert decode_checksum(b64) == digest


def test_decode_checksum_invalid() -> None:
    with pytest.raises(ValueError):
        decode_checksum("not$$valid")
