import pytest

pytest.importorskip("pyldpc")

from genecoder.ldpc_codec import encode_data_ldpc, decode_data_ldpc

def test_ldpc_roundtrip():
    data = b"LDPC test"
    encoded, info = encode_data_ldpc(data)
    decoded, _ = decode_data_ldpc(encoded, info)
    assert decoded.startswith(data[: len(decoded)])
