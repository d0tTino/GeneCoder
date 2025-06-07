import pytest

from dna_encoder import encoder  # noqa: E402


def test_encode_empty():
    assert encoder.encode_base4(b"") == ""


def test_encode_single_bytes():
    assert encoder.encode_base4(b"\x00") == "AAAA"  # 00000000
    assert encoder.encode_base4(b"\x0F") == "AATT"  # 00001111
    assert encoder.encode_base4(b"\xF0") == "TTAA"  # 11110000
    assert encoder.encode_base4(b"\x55") == "CCCC"  # 01010101
    assert encoder.encode_base4(b"\xAA") == "GGGG"  # 10101010
    assert encoder.encode_base4(b"\xFF") == "TTTT"  # 11111111


def test_encode_multiple_bytes():
    # H = 0x48 = 01001000 -> CAGA
    # i = 0x69 = 01101001 -> CGGC
    assert encoder.encode_base4(b"Hi") == "CAGACGGC"
    assert (
        encoder.encode_base4(b"\x01\x23\x45\x67\x89\xAB\xCD\xEF")
        == "AAACAGATCACCCGCTGAGCGGGTTATCTGTT"
    )


def test_decode_empty():
    assert encoder.decode_base4("") == b""


def test_decode_simple_sequences():
    assert encoder.decode_base4("AAAA") == b"\x00"
    assert encoder.decode_base4("AATT") == b"\x0F"
    assert encoder.decode_base4("TTAA") == b"\xF0"
    assert encoder.decode_base4("CCCC") == b"\x55"
    assert encoder.decode_base4("GGGG") == b"\xAA"
    assert encoder.decode_base4("TTTT") == b"\xFF"


def test_decode_multiple_bytes_sequence():
    assert encoder.decode_base4("CAGACGGC") == b"Hi"


def test_decode_invalid_character():
    with pytest.raises(ValueError, match="Invalid character in DNA sequence: X"):
        encoder.decode_base4("ACGTX")
    with pytest.raises(ValueError, match="Invalid character in DNA sequence: B"):
        encoder.decode_base4("ABCG")
    with pytest.raises(ValueError, match="Invalid character in DNA sequence: a"):
        encoder.decode_base4("aCGT")


def test_decode_invalid_length():
    with pytest.raises(ValueError, match="Invalid DNA sequence length for byte conversion."):
        encoder.decode_base4("A")
    with pytest.raises(ValueError, match="Invalid DNA sequence length for byte conversion."):
        encoder.decode_base4("ACA")
    with pytest.raises(ValueError, match="Invalid DNA sequence length for byte conversion."):
        encoder.decode_base4("AA")
    with pytest.raises(ValueError, match="Invalid DNA sequence length for byte conversion."):
        encoder.decode_base4("AAA")
    with pytest.raises(ValueError, match="Invalid DNA sequence length for byte conversion."):
        encoder.decode_base4("AAAAA")


def test_roundtrip_empty():
    assert encoder.decode_base4(encoder.encode_base4(b"")) == b""


def test_roundtrip_simple_bytes():
    bytes_to_test = [b"A", b"\x12", b"\x00", b"\xFF", b"\x5A", b"\xA5"]
    for val in bytes_to_test:
        assert encoder.decode_base4(encoder.encode_base4(val)) == val


def test_roundtrip_text():
    texts_to_test = [b"Hello", b"Base-4", b"DNA Encoder/Decoder Test!"]
    for text in texts_to_test:
        assert encoder.decode_base4(encoder.encode_base4(text)) == text


def test_roundtrip_longer_sequence():
    long_bytes = (
        b"\xDE\xAD\xBE\xEF\xCA\xFE\xBA\xBE\x00\x11\x22\x33"
        b"\x44\x55\x66\x77\x88\x99\xAA\xBB\xCC\xDD\xEE\xFF"
    )
    assert encoder.decode_base4(encoder.encode_base4(long_bytes)) == long_bytes
