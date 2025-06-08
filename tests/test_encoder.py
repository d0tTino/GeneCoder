import pytest

from genecoder.encoders import (
    encode_base4_direct,
    decode_base4_direct,
)

def test_encode_empty():
    assert encode_base4_direct(b"") == ""


def test_encode_single_bytes():
    assert encode_base4_direct(b"\x00") == "AAAA"  # 00000000
    assert encode_base4_direct(b"\x0F") == "AATT"  # 00001111
    assert encode_base4_direct(b"\xF0") == "TTAA"  # 11110000
    assert encode_base4_direct(b"\x55") == "CCCC"  # 01010101
    assert encode_base4_direct(b"\xAA") == "GGGG"  # 10101010
    assert encode_base4_direct(b"\xFF") == "TTTT"  # 11111111


def test_encode_multiple_bytes():
    # H = 0x48 = 01001000 -> CAGA
    # i = 0x69 = 01101001 -> CGGC
    assert encode_base4_direct(b"Hi") == "CAGACGGC"
    assert (
        encode_base4_direct(b"\x01\x23\x45\x67\x89\xAB\xCD\xEF")
        == "AAACAGATCACCCGCTGAGCGGGTTATCTGTT"
    )


def test_decode_empty():
    decoded_data, errors = decode_base4_direct("")
    assert decoded_data == b""
    assert errors == []


def test_decode_simple_sequences():
    decoded_data, errors = decode_base4_direct("AAAA")
    assert decoded_data == b"\x00"
    assert errors == []
    decoded_data, errors = decode_base4_direct("AATT")
    assert decoded_data == b"\x0F"
    assert errors == []
    decoded_data, errors = decode_base4_direct("TTAA")
    assert decoded_data == b"\xF0"
    assert errors == []
    decoded_data, errors = decode_base4_direct("CCCC")
    assert decoded_data == b"\x55"
    assert errors == []
    decoded_data, errors = decode_base4_direct("GGGG")
    assert decoded_data == b"\xAA"
    assert errors == []
    decoded_data, errors = decode_base4_direct("TTTT")
    assert decoded_data == b"\xFF"
    assert errors == []


def test_decode_multiple_bytes_sequence():
    decoded_data, errors = decode_base4_direct("CAGACGGC")
    assert decoded_data == b"Hi"
    assert errors == []


def test_decode_invalid_character():
    with pytest.raises(ValueError):
        decode_base4_direct("ACGTX")
    with pytest.raises(ValueError):
        decode_base4_direct("ABCG")
    with pytest.raises(ValueError):
        decode_base4_direct("aCGT")


def test_decode_invalid_length():
    with pytest.raises(ValueError):
        decode_base4_direct("A")
    with pytest.raises(ValueError):
        decode_base4_direct("ACA")
    with pytest.raises(ValueError):
        decode_base4_direct("AA")
    with pytest.raises(ValueError):
        decode_base4_direct("AAA")
    with pytest.raises(ValueError):
        decode_base4_direct("AAAAA")


def test_roundtrip_empty():
    decoded, errors = decode_base4_direct(encode_base4_direct(b""))
    assert decoded == b""
    assert errors == []


def test_roundtrip_simple_bytes():
    bytes_to_test = [b"A", b"\x12", b"\x00", b"\xFF", b"\x5A", b"\xA5"]
    for val in bytes_to_test:
        decoded, errors = decode_base4_direct(encode_base4_direct(val))
        assert decoded == val
        assert errors == []


def test_roundtrip_text():
    texts_to_test = [b"Hello", b"Base-4", b"DNA Encoder/Decoder Test!"]
    for text in texts_to_test:
        decoded, errors = decode_base4_direct(encode_base4_direct(text))
        assert decoded == text
        assert errors == []


def test_roundtrip_longer_sequence():
    long_bytes = (
        b"\xDE\xAD\xBE\xEF\xCA\xFE\xBA\xBE\x00\x11\x22\x33"
        b"\x44\x55\x66\x77\x88\x99\xAA\xBB\xCC\xDD\xEE\xFF"
    )
    decoded, errors = decode_base4_direct(encode_base4_direct(long_bytes))
    assert decoded == long_bytes
    assert errors == []
