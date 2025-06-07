import pytest

from genecoder.formats import to_fasta, from_fasta  # noqa: E402


def test_empty_sequence():
    assert to_fasta("", "empty_seq") == ">empty_seq\n"


def test_short_sequence():
    assert to_fasta("ATGC", "short_seq") == ">short_seq\nATGC\n"


def test_short_sequence_explicit_line_width():
    assert to_fasta("ATGC", "short_seq_lw", 10) == ">short_seq_lw\nATGC\n"


def test_sequence_equals_line_width():
    assert to_fasta("ATGCATGC", "seq_eq_lw", 8) == ">seq_eq_lw\nATGCATGC\n"


def test_sequence_multiple_lines():
    expected = ">seq_multi_line\nATGC\nATGC\nATGC\n"
    assert to_fasta("ATGCATGCATGC", "seq_multi_line", 4) == expected


def test_sequence_last_line_shorter():
    expected_output = ">seq_last_short\nATGC\nATGC\nA\n"
    assert to_fasta("ATGCATGCA", "seq_last_short", 4) == expected_output


def test_different_line_width():
    expected_output = ">seq_lw_5\nATGCA\nTGCAT\nGCATG\nC\n"
    assert to_fasta("ATGCATGCATGCATGC", "seq_lw_5", 5) == expected_output


def test_header_preservation():
    complex_header = "seq1 | organism=human | length=10"
    expected_output = f">{complex_header}\nATGC\n"
    assert to_fasta("ATGC", complex_header) == expected_output


def test_header_with_special_chars():
    header = "test_seq_123 ID:XYZ|source:ABC Ch:5 Pos:100-200; Note=Test data"
    expected_output = f">{header}\nSEQUENCE\n"
    assert to_fasta("SEQUENCE", header, 80) == expected_output


def test_line_width_zero():
    with pytest.raises(ValueError, match="line_width must be a positive integer."):
        to_fasta("ATGC", "header_lw_zero", 0)


def test_line_width_negative():
    with pytest.raises(ValueError, match="line_width must be a positive integer."):
        to_fasta("ATGC", "header_lw_neg", -1)


def test_line_width_non_integer():
    with pytest.raises(ValueError, match="line_width must be a positive integer."):
        to_fasta("ATGC", "header_lw_float", 5.5)  # type: ignore
    with pytest.raises(ValueError, match="line_width must be a positive integer."):
        to_fasta("ATGC", "header_lw_str", "abc")  # type: ignore


def test_from_fasta_empty_string():
    assert from_fasta("") == []


def test_from_fasta_no_header_prefix():
    assert from_fasta("ATGC\nATGC") == []
    assert from_fasta("Just some random text\nNot a fasta") == []


def test_from_fasta_single_record_single_line_seq():
    content = ">seq1 description\nATGCATGC"
    expected = [("seq1 description", "ATGCATGC")]
    assert from_fasta(content) == expected


def test_from_fasta_single_record_multi_line_seq():
    content = ">seq2\nATGC\nGTCA\n"
    expected = [("seq2", "ATGCGTCA")]
    assert from_fasta(content) == expected


def test_from_fasta_header_only_no_sequence():
    content = ">seq3 header only"
    expected = [("seq3 header only", "")]
    assert from_fasta(content) == expected

    content_with_newline = ">seq3b header only\n"
    expected_with_newline = [("seq3b header only", "")]
    assert from_fasta(content_with_newline) == expected_with_newline


def test_from_fasta_sequence_internal_whitespace():
    content = ">seq4\nAT GC\n GT CA "
    expected = [("seq4", "ATGCGTCA")]
    assert from_fasta(content) == expected


def test_from_fasta_multi_record():
    content = ">seqA\nAA\n>seqB\nBB\nCC"
    expected = [("seqA", "AA"), ("seqB", "BBCC")]
    assert from_fasta(content) == expected


def test_from_fasta_blank_lines_in_sequence():
    content = ">seqC\nAA\n\nGG\nTT"
    expected = [("seqC", "AAGGTT")]
    assert from_fasta(content) == expected


def test_from_fasta_blank_lines_between_records():
    content = ">seqD\nDD\n\n>seqE\nEE"
    expected = [("seqD", "DD"), ("seqE", "EE")]
    assert from_fasta(content) == expected


def test_from_fasta_leading_trailing_whitespace_on_lines():
    content = "  >seqF Header  \n  ATGC  \n  GTCA  \n"
    expected = [("seqF Header", "ATGCGTCA")]
    assert from_fasta(content) == expected


def test_from_fasta_no_newline_at_end():
    content = ">seqG\nATGC"
    expected = [("seqG", "ATGC")]
    assert from_fasta(content) == expected


def test_from_fasta_mixed_whitespace_and_content():
    content = "\n>seqH\n  AG\n  \n  CT \n>seqI\n  TC\nGA"
    expected = [("seqH", "AGCT"), ("seqI", "TCGA")]
    assert from_fasta(content) == expected


def test_from_fasta_multiple_headers_no_sequence():
    content = ">seq1\n>seq2\n>seq3"
    expected = [("seq1", ""), ("seq2", ""), ("seq3", "")]
    assert from_fasta(content) == expected


def test_from_fasta_sequence_before_first_header():
    content = "ATGC\n>seq1\nCGTA"
    expected = [("seq1", "CGTA")]
    assert from_fasta(content) == expected


def test_from_fasta_only_whitespace_lines():
    content = "\n  \n\t\n"
    assert from_fasta(content) == []


def test_from_fasta_header_with_various_chars():
    header = "id|123 status:active gene=XYZ; note=test data"
    content = f">{header}\nATGC"
    expected = [(header, "ATGC")]
    assert from_fasta(content) == expected
