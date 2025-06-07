import pytest

from genecoder.error_detection import (
    _calculate_gc_parity,
    add_parity_to_sequence,
    strip_and_verify_parity,
    PARITY_RULE_GC_EVEN_A_ODD_T,
)


def test_gc_parity_even():
    assert _calculate_gc_parity("AAGG") == "A"
    assert _calculate_gc_parity("CCGG") == "A"


def test_gc_parity_odd():
    assert _calculate_gc_parity("AAGC") == "A"
    assert _calculate_gc_parity("GCT") == "A"


def test_gc_parity_no_gc():
    assert _calculate_gc_parity("AATT") == "A"


def test_gc_parity_all_gc():
    assert _calculate_gc_parity("GGCC") == "A"
    assert _calculate_gc_parity("GCG") == "T"


def test_gc_parity_empty_block():
    assert _calculate_gc_parity("") == "A"


def test_add_parity_simple():
    assert add_parity_to_sequence("GCGCAT", 3, PARITY_RULE_GC_EVEN_A_ODD_T) == "GCGTCATT"


def test_add_parity_k_equals_len():
    assert add_parity_to_sequence("ATGC", 4, PARITY_RULE_GC_EVEN_A_ODD_T) == "ATGCA"


def test_add_parity_len_not_multiple_of_k():
    assert (
        add_parity_to_sequence("ATGCATG", 3, PARITY_RULE_GC_EVEN_A_ODD_T)
        == "ATGTCATTGT"
    )


def test_add_parity_empty_sequence():
    assert add_parity_to_sequence("", 3, PARITY_RULE_GC_EVEN_A_ODD_T) == ""


def test_add_parity_invalid_k():
    with pytest.raises(ValueError, match="k_value must be a positive integer."):
        add_parity_to_sequence("AG", 0, PARITY_RULE_GC_EVEN_A_ODD_T)
    with pytest.raises(ValueError, match="k_value must be a positive integer."):
        add_parity_to_sequence("AG", -1, PARITY_RULE_GC_EVEN_A_ODD_T)


def test_add_parity_unknown_rule():
    with pytest.raises(NotImplementedError, match="Parity rule 'unknown_rule' is not implemented."):
        add_parity_to_sequence("AG", 3, "unknown_rule")


def test_strip_verify_no_errors():
    assert strip_and_verify_parity("GCGTCATT", 3, PARITY_RULE_GC_EVEN_A_ODD_T) == (
        "GCGCAT",
        [],
    )


def test_strip_verify_with_errors():
    assert strip_and_verify_parity("GCGATCATT", 3, PARITY_RULE_GC_EVEN_A_ODD_T) == (
        "GCGTCA",
        [0],
    )


def test_strip_verify_multiple_errors():
    assert strip_and_verify_parity("GCGATCATA", 3, PARITY_RULE_GC_EVEN_A_ODD_T) == (
        "GCGTCA",
        [0],
    )


def test_strip_verify_last_block_partial_data():
    assert strip_and_verify_parity("ATGTCATTGT", 3, PARITY_RULE_GC_EVEN_A_ODD_T) == (
        "ATGCATG",
        [],
    )
    assert strip_and_verify_parity("ATGTCATTGA", 3, PARITY_RULE_GC_EVEN_A_ODD_T) == (
        "ATGCATG",
        [],
    )


def test_strip_verify_empty_sequence():
    assert strip_and_verify_parity("", 3, PARITY_RULE_GC_EVEN_A_ODD_T) == ("", [])


def test_strip_verify_malformed_length():
    pass


def test_strip_verify_invalid_k():
    with pytest.raises(ValueError, match="k_value must be a positive integer."):
        strip_and_verify_parity("AG", 0, PARITY_RULE_GC_EVEN_A_ODD_T)
    with pytest.raises(ValueError, match="k_value must be a positive integer."):
        strip_and_verify_parity("AG", -1, PARITY_RULE_GC_EVEN_A_ODD_T)


def test_strip_verify_unknown_rule():
    with pytest.raises(NotImplementedError, match="Parity rule 'unknown_rule' is not implemented."):
        strip_and_verify_parity("AGTT", 2, "unknown_rule")
