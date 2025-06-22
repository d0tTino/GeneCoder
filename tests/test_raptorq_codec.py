import pytest

from genecoder.raptorq_codec import _HAS_RAPTORQ, encode_data_raptorq, decode_data_raptorq

pytestmark = pytest.mark.skipif(not _HAS_RAPTORQ, reason="raptorq not installed")


def test_raptorq_roundtrip():
    data = b"hello rq"
    encoded, info = encode_data_raptorq(data, symbol_size=4)
    decoded, corrected = decode_data_raptorq(encoded, info)
    assert decoded == data
    assert corrected == 0
