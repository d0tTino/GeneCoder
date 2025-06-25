import pytest
from genecoder.raptorq_codec import _HAS_RAPTORQ, encode_data_raptorq, decode_data_raptorq, raptorq

pytestmark = pytest.mark.skipif(not _HAS_RAPTORQ, reason="raptorq not installed")


def test_raptorq_decode_failure(monkeypatch):
    data = b"rq"
    encoded, info = encode_data_raptorq(data, symbol_size=4)

    class FakeDecoder:
        def __init__(self, symbol_size, orig_len):
            pass
        def decode(self, payload):
            return None

    monkeypatch.setattr(raptorq, "Decoder", FakeDecoder)
    with pytest.raises(ValueError, match="RaptorQ decode failed"):
        decode_data_raptorq(encoded, info)
