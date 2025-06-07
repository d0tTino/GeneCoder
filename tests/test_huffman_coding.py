import pytest

from genecoder.huffman_coding import encode_huffman, decode_huffman  # noqa: E402
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T  # noqa: E402


def test_encode_empty():
    assert encode_huffman(b"") == ("", {}, 0)


def test_encode_single_unique_byte():
    data = b"AAAAA"
    dna, table, pad = encode_huffman(data)
    assert table == {65: "0"}
    assert pad == 1
    assert dna == "AAA"


def test_encode_simple_string_properties():
    data = b"aabbc"
    dna, table, pad = encode_huffman(data)
    assert len(table) == 3
    assert ord("a") in table
    assert ord("b") in table
    assert ord("c") in table
    expected_binary_len = sum(len(table[b]) for b in data)
    assert pad in [0, 1]
    expected_padded_len = expected_binary_len + pad
    assert expected_padded_len % 2 == 0
    assert len(dna) * 2 == expected_padded_len


def test_encode_needs_padding():
    data = b"abb"
    dna, table, pad = encode_huffman(data)
    binary_str = "".join(table[b] for b in data)
    if len(binary_str) % 2 != 0:
        assert pad == 1
    else:
        assert pad == 0
    assert len(dna) * 2 == len(binary_str) + pad


def _round_trip_no_parity(data_bytes):
    dna_no, table_no, pad_no = encode_huffman(data_bytes, add_parity=False)
    decoded, errors = decode_huffman(dna_no, table_no, pad_no, check_parity=False)
    assert decoded == data_bytes
    assert errors == []


def test_round_trip_empty():
    _round_trip_no_parity(b"")


def test_round_trip_single_byte():
    _round_trip_no_parity(b"A")


def test_round_trip_repeated_bytes():
    _round_trip_no_parity(b"BBBBBB")


def test_round_trip_simple_string():
    _round_trip_no_parity(b"hello world")


def test_round_trip_varied_frequencies():
    _round_trip_no_parity(b"aaabbc")


def test_round_trip_all_bytes():
    _round_trip_no_parity(bytes(range(256)))


def test_round_trip_long_string():
    long_data = (
        b"This is a longer test string with many characters and varying frequencies to robustly test Huffman coding." * 5
    )
    _round_trip_no_parity(long_data)


def test_round_trip_two_chars_need_padding():
    _round_trip_no_parity(b"AC")


def test_decode_invalid_dna_character():
    dna, table, pad = encode_huffman(b"A", add_parity=False)
    with pytest.raises(ValueError, match="Invalid DNA character 'X' in sequence."):
        decode_huffman("AGCX", table, pad, check_parity=False)


def test_decode_invalid_padding_too_large():
    with pytest.raises(ValueError, match="Invalid padding: 3 padding bits claimed, but only 2 bits available."):
        decode_huffman("A", {65: "0"}, 3, check_parity=False)


def test_decode_invalid_padding_non_zero_bit():
    table_for_a = {65: "0"}
    with pytest.raises(ValueError, match="Invalid padding bits: expected all '0's but found '1'."):
        decode_huffman("T", table_for_a, 1, check_parity=False)


def test_decode_code_not_in_table():
    dna, table, pad = encode_huffman(b"A", add_parity=False)
    with pytest.raises(ValueError, match="Corrupted data or incorrect Huffman table: remaining unparsed bits '1'."):
        decode_huffman("G", table, pad, check_parity=False)


def test_decode_incomplete_code_at_end():
    custom_table = {ord('X'): "001"}
    with pytest.raises(ValueError, match="Corrupted data or incorrect Huffman table: remaining unparsed bits '00'."):
        decode_huffman("A", custom_table, 0, check_parity=False)


def test_encode_huffman_with_parity():
    data = b"aabbc"
    k_val = 4
    dna_no, _, _ = encode_huffman(data, add_parity=False)
    dna_with, _, _ = encode_huffman(data, add_parity=True, k_value=k_val, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T)
    expected_parity_bits = (len(dna_no) + k_val - 1) // k_val if dna_no else 0
    assert len(dna_with) == len(dna_no) + expected_parity_bits


def test_decode_huffman_with_parity_no_errors():
    data = b"hello"
    k_val = 3
    dna_with, table, pad = encode_huffman(data, add_parity=True, k_value=k_val, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T)
    decoded, errors = decode_huffman(
        dna_with, table, pad, check_parity=True, k_value=k_val, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
    )
    assert decoded == data
    assert errors == []


def test_decode_huffman_with_parity_with_errors():
    data = b"worlddata"
    k_val = 3
    dna_with, table, pad = encode_huffman(data, add_parity=True, k_value=k_val, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T)
    if len(dna_with) <= k_val:
        pytest.skip("DNA sequence too short to corrupt a parity bit meaningfully.")
    original_char = dna_with[k_val]
    corrupted_char = "A" if original_char != "A" else "T"
    corrupted = dna_with[:k_val] + corrupted_char + dna_with[k_val + 1:]
    decoded, errors = decode_huffman(
        corrupted, table, pad, check_parity=True, k_value=k_val, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
    )
    assert decoded == data
    assert 0 in errors


def _round_trip_with_parity(data_bytes, k_value):
    dna, table, pad = encode_huffman(
        data_bytes, add_parity=True, k_value=k_value, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
    )
    decoded, errors = decode_huffman(
        dna, table, pad, check_parity=True, k_value=k_value, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
    )
    assert decoded == data_bytes
    assert errors == []


def test_round_trip_huffman_with_parity_various_k():
    _round_trip_with_parity(b"Parity test for Huffman!", 3)
    _round_trip_with_parity(b"Another example with different k.", 5)
    _round_trip_with_parity(b"Short", 2)
    _round_trip_with_parity(b"", 3)
    _round_trip_with_parity(b"X", 1)
