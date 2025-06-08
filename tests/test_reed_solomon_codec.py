import pytest

from genecoder.reed_solomon_codec import encode_data_rs, decode_data_rs


def test_rs_roundtrip_no_errors():
    data = b"Hello RS"
    encoded, nsym = encode_data_rs(data, nsym=10)
    decoded, corrected = decode_data_rs(encoded, nsym)
    assert decoded == data
    assert corrected == 0


def test_rs_corrects_burst_errors():
    data = b"0123456789ABCDEF"
    encoded, nsym = encode_data_rs(data, nsym=10)
    corrupted = bytearray(encoded)
    for i in range(4):
        corrupted[i] ^= 0xFF
    decoded, corrected = decode_data_rs(bytes(corrupted), nsym)
    assert decoded == data
    assert corrected == 4


def test_rs_too_many_errors():
    data = b"0123456789ABCDEF"
    encoded, nsym = encode_data_rs(data, nsym=10)
    corrupted = bytearray(encoded)
    for i in range(6):
        corrupted[i] ^= 0xFF
    with pytest.raises(ValueError):
        decode_data_rs(bytes(corrupted), nsym)
