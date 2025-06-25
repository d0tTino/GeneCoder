import pytest
from genecoder.ldpc_codec import _HAS_PYLDPC, encode_data_ldpc, decode_data_ldpc

pytestmark = pytest.mark.skipif(not _HAS_PYLDPC, reason="pyldpc not installed")


def test_ldpc_decode_corrections():
    data = b"LDPC" * 2
    encoded, info = encode_data_ldpc(data)
    corrupted = bytearray(encoded)
    corrupted[0] ^= 1
    decoded, corrections = decode_data_ldpc(bytes(corrupted), info)
    assert decoded.startswith(data)
    assert corrections > 0
