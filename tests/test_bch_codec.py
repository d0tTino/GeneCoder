import pytest

from genecoder.bch_codec import _HAS_BCHLIB, encode_data_bch, decode_data_bch

pytestmark = pytest.mark.skipif(not _HAS_BCHLIB, reason="bchlib not installed")


def test_bch_roundtrip():
    data = b"hello bch"
    encoded, info = encode_data_bch(data, m=5, t=2)
    decoded, corrected = decode_data_bch(encoded, info)
    assert decoded == data
    assert corrected >= 0
