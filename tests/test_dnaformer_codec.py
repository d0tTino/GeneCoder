import pytest

pytest.importorskip("dnaformer")

from genecoder.dnaformer_codec import encode_data_dnaformer, decode_data_dnaformer


def test_dnaformer_roundtrip() -> None:
    data = b"dnaformer test"
    encoded, info = encode_data_dnaformer(data)
    decoded, corrected = decode_data_dnaformer(encoded, info)
    assert decoded == data
    assert corrected >= 0
