import pytest

from genecoder.fec.framed import _HAS_FRAMED, encode_data_framed, decode_data_framed

pytestmark = pytest.mark.skipif(not _HAS_FRAMED, reason="FrameD not installed")


def test_framed_roundtrip() -> None:
    data = b"hello framed"
    encoded, info = encode_data_framed(data)
    decoded, corrected = decode_data_framed(encoded, info)
    assert decoded == data
    assert corrected >= 0
