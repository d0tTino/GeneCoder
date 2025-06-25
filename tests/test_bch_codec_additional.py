import pytest
from genecoder.bch_codec import _HAS_BCHLIB, encode_data_bch, decode_data_bch, bchlib

pytestmark = pytest.mark.skipif(not _HAS_BCHLIB, reason="bchlib not installed")


def test_bch_decode_failure(monkeypatch):
    data = b"fail"
    encoded, info = encode_data_bch(data, m=5, t=2)

    class FakeBCH:
        def __init__(self, m, t):
            self.ecc_bytes = len(encoded) - len(data)

        def decode(self, data_bytes, ecc):
            return None, 0

    monkeypatch.setattr(bchlib, "BCH", FakeBCH)
    with pytest.raises(ValueError, match="BCH decode failed"):
        decode_data_bch(encoded, info)
