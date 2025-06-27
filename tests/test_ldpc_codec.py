import pytest

from genecoder.ldpc_codec import _HAS_PYLDPC, encode_data_ldpc, decode_data_ldpc

pytestmark = pytest.mark.skipif(not _HAS_PYLDPC, reason="pyldpc not installed")

def test_ldpc_roundtrip():
    data = b"LDPC test"
    encoded, info = encode_data_ldpc(data)
    decoded, _ = decode_data_ldpc(encoded, info)
    assert decoded.startswith(data[: len(decoded)])
