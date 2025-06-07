import pytest

from genecoder.encoders import encode_base4_direct, decode_base4_direct  # noqa: E402
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T  # noqa: E402


def test_encode_empty():
    assert encode_base4_direct(b"") == ""


def test_encode_single_byte_zero():
    assert encode_base4_direct(b"\x00") == "AAAA"


def test_encode_single_byte_max():
    assert encode_base4_direct(b"\xff") == "TTTT"


def test_encode_ascii_char():
    assert encode_base4_direct(b"A") == "CAAC"


def test_encode_multiple_bytes():
    assert encode_base4_direct(b"Hi") == "CAGACGGC"


def test_encode_byte_sequence():
    assert encode_base4_direct(b"\x12\x34\xAB\xCD") == "ACAGATCAGGGTTATC"


def test_decode_empty():
    decoded_data, errors = decode_base4_direct("")
    assert decoded_data == b""
    assert errors == []


def test_decode_valid_sequence_aaaa():
    decoded_data, errors = decode_base4_direct("AAAA")
    assert decoded_data == b"\x00"
    assert errors == []


def test_decode_valid_sequence_gggg():
    decoded_data, errors = decode_base4_direct("TTTT")
    assert decoded_data == b"\xff"
    assert errors == []


def test_decode_ascii_char_reverse():
    decoded_data, errors = decode_base4_direct("CAAC")
    assert decoded_data == b"A"
    assert errors == []


def test_decode_multiple_bytes_reverse():
    decoded_data, errors = decode_base4_direct("CAGACGGC")
    assert decoded_data == b"Hi"
    assert errors == []


def test_decode_byte_sequence_reverse():
    decoded_data, errors = decode_base4_direct("ACAGATCAGGGTTATC")
    assert decoded_data == b"\x12\x34\xAB\xCD"
    assert errors == []


def test_round_trip_empty_no_parity():
    data = b""
    encoded = encode_base4_direct(data)
    decoded, errors = decode_base4_direct(encoded)
    assert decoded == data
    assert errors == []


def test_round_trip_simple_string_no_parity():
    data = b"Hello GeneCoder!"
    encoded = encode_base4_direct(data)
    decoded, errors = decode_base4_direct(encoded)
    assert decoded == data
    assert errors == []


def test_round_trip_various_bytes_no_parity():
    data = b"\x00\x01\xFA\x80\x7F\xff"
    encoded = encode_base4_direct(data)
    decoded, errors = decode_base4_direct(encoded)
    assert decoded == data
    assert errors == []


def test_decode_invalid_character():
    with pytest.raises(ValueError):
        decode_base4_direct("AGCX")


def test_decode_invalid_character_lowercase():
    with pytest.raises(ValueError):
        decode_base4_direct("agct")


def test_decode_invalid_length_short():
    with pytest.raises(ValueError):
        decode_base4_direct("AGC")


def test_decode_invalid_length_long():
    with pytest.raises(ValueError):
        decode_base4_direct("AGCTA")


def test_encode_base4_with_parity():
    expected_dna_with_parity = "ACATGATTCAT"
    actual_dna_with_parity = encode_base4_direct(
        b"\x12\x34", add_parity=True, k_value=3, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
    )
    assert actual_dna_with_parity == expected_dna_with_parity


def test_decode_base4_with_parity_no_errors():
    dna_with_parity = "ACATGATTCAT"
    original_data = b"\x12\x34"
    decoded_data, errors = decode_base4_direct(
        dna_with_parity, check_parity=True, k_value=3, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
    )
    assert decoded_data == original_data
    assert errors == []


def test_decode_base4_with_parity_with_errors():
    corrupted_dna = "ACAAGATTCAT"
    original_data_stripped = b"\x12\x34"
    decoded_data, errors = decode_base4_direct(
        corrupted_dna, check_parity=True, k_value=3, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
    )
    assert decoded_data == original_data_stripped
    assert errors == [0]


def test_round_trip_base4_with_parity():
    data = b"TestParity!"
    k_val = 5
    encoded_dna = encode_base4_direct(
        data, add_parity=True, k_value=k_val, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
    )
    decoded_data, errors = decode_base4_direct(
        encoded_dna, check_parity=True, k_value=k_val, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
    )
    assert decoded_data == data
    assert errors == []
