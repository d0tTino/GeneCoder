import pytest

pytest.importorskip("pyfinite")

from genecoder.fountain_codec import encode_data_fountain, decode_data_fountain

def test_fountain_roundtrip():
    data = b"Fountain test data"
    encoded, info = encode_data_fountain(data, chunk_size=5)
    decoded, _ = decode_data_fountain(encoded, info)
    assert decoded == data


def test_fountain_empty_data():
    encoded, info = encode_data_fountain(b"", chunk_size=5)
    assert encoded == b""
    assert info["orig_len"] == 0
    decoded, _ = decode_data_fountain(encoded, info)
    assert decoded == b""
