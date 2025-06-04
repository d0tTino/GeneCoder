import unittest
from genecoder.formats import to_fasta, from_fasta # Import from_fasta

class TestFastaFormatting(unittest.TestCase):

    def test_empty_sequence(self):
        self.assertEqual(to_fasta("", "empty_seq"), ">empty_seq\n")

    def test_short_sequence(self):
        # Sequence shorter than default line_width (60)
        self.assertEqual(to_fasta("ATGC", "short_seq"), ">short_seq\nATGC\n")

    def test_short_sequence_explicit_line_width(self):
        # Sequence shorter than specified line_width
        self.assertEqual(to_fasta("ATGC", "short_seq_lw", 10), ">short_seq_lw\nATGC\n")

    def test_sequence_equals_line_width(self):
        self.assertEqual(to_fasta("ATGCATGC", "seq_eq_lw", 8), ">seq_eq_lw\nATGCATGC\n")

    def test_sequence_multiple_lines(self):
        expected_output = ">seq_multi_line\nATGC\nATGC\nATGC\n"
        self.assertEqual(to_fasta("ATGCATGCATGC", "seq_multi_line", 4), expected_output)

    def test_sequence_last_line_shorter(self):
        expected_output = ">seq_last_short\nATGC\nATGC\nA\n"
        self.assertEqual(to_fasta("ATGCATGCA", "seq_last_short", 4), expected_output)

    def test_different_line_width(self):
        # Test with a line_width that results in a short last line
        expected_output = ">seq_lw_5\nATGCA\nTGCAT\nGCATG\nC\n"
        self.assertEqual(to_fasta("ATGCATGCATGCATGC", "seq_lw_5", 5), expected_output)

    def test_header_preservation(self):
        complex_header = "seq1 | organism=human | length=10"
        expected_output = f">{complex_header}\nATGC\n"
        self.assertEqual(to_fasta("ATGC", complex_header), expected_output)

    def test_header_with_special_chars(self):
        # FASTA headers can be quite diverse
        header = "test_seq_123 ID:XYZ|source:ABC Ch:5 Pos:100-200; Note=Test data"
        expected_output = f">{header}\nSEQUENCE\n"
        self.assertEqual(to_fasta("SEQUENCE", header, 80), expected_output)

    # Tests for to_fasta error handling for line_width
    def test_line_width_zero(self):
        with self.assertRaisesRegex(ValueError, "line_width must be a positive integer."):
            to_fasta("ATGC", "header_lw_zero", 0)

    def test_line_width_negative(self):
        with self.assertRaisesRegex(ValueError, "line_width must be a positive integer."):
            to_fasta("ATGC", "header_lw_neg", -1)

    def test_line_width_non_integer(self):
        # Although the type hint is int, test runtime behavior for robustness
        with self.assertRaisesRegex(ValueError, "line_width must be a positive integer."):
            to_fasta("ATGC", "header_lw_float", 5.5) # type: ignore
        with self.assertRaisesRegex(ValueError, "line_width must be a positive integer."):
            to_fasta("ATGC", "header_lw_str", "abc") # type: ignore


if __name__ == '__main__':
    unittest.main()


class TestFastaParsing(unittest.TestCase):

    def test_from_fasta_empty_string(self):
        self.assertEqual(from_fasta(""), [])

    def test_from_fasta_no_header_prefix(self):
        # Lines without ">" prefix before any valid header are ignored
        self.assertEqual(from_fasta("ATGC\nATGC"), [])
        self.assertEqual(from_fasta("Just some random text\nNot a fasta"), [])

    def test_from_fasta_single_record_single_line_seq(self):
        content = ">seq1 description\nATGCATGC"
        expected = [("seq1 description", "ATGCATGC")]
        self.assertEqual(from_fasta(content), expected)

    def test_from_fasta_single_record_multi_line_seq(self):
        content = ">seq2\nATGC\nGTCA\n"
        expected = [("seq2", "ATGCGTCA")]
        self.assertEqual(from_fasta(content), expected)

    def test_from_fasta_header_only_no_sequence(self):
        content = ">seq3 header only"
        expected = [("seq3 header only", "")]
        self.assertEqual(from_fasta(content), expected)
        
        content_with_newline = ">seq3b header only\n"
        expected_with_newline = [("seq3b header only", "")]
        self.assertEqual(from_fasta(content_with_newline), expected_with_newline)

    def test_from_fasta_sequence_internal_whitespace(self):
        # The current from_fasta implementation uses `"".join(line.split())` for sequence lines,
        # which removes ALL internal whitespace from each line before concatenating.
        content = ">seq4\nAT GC\n GT CA " # Each sequence line is processed by strip() then "".join(line.split())
                                         # "AT GC" -> "ATGC"
                                         # " GT CA " -> "GTCA"
        expected = [("seq4", "ATGCGTCA")] # Concatenated: "ATGCGTCA"
        self.assertEqual(from_fasta(content), expected)

    def test_from_fasta_multi_record(self):
        content = ">seqA\nAA\n>seqB\nBB\nCC"
        expected = [("seqA", "AA"), ("seqB", "BBCC")]
        self.assertEqual(from_fasta(content), expected)

    def test_from_fasta_blank_lines_in_sequence(self):
        content = ">seqC\nAA\n\nGG\nTT" # Blank lines are skipped
        expected = [("seqC", "AAGGTT")]
        self.assertEqual(from_fasta(content), expected)

    def test_from_fasta_blank_lines_between_records(self):
        content = ">seqD\nDD\n\n>seqE\nEE"
        expected = [("seqD", "DD"), ("seqE", "EE")]
        self.assertEqual(from_fasta(content), expected)

    def test_from_fasta_leading_trailing_whitespace_on_lines(self):
        # `line.strip()` handles leading/trailing whitespace for header and sequence lines.
        # `"".join(line.split())` for sequence lines also handles internal whitespace.
        content = "  >seqF Header  \n  ATGC  \n  GTCA  \n"
        expected = [("seqF Header", "ATGCGTCA")] # "ATGC" and "GTCA" after processing
        self.assertEqual(from_fasta(content), expected)

    def test_from_fasta_no_newline_at_end(self):
        content = ">seqG\nATGC"
        expected = [("seqG", "ATGC")]
        self.assertEqual(from_fasta(content), expected)

    def test_from_fasta_mixed_whitespace_and_content(self):
        # `line.strip()` and `"".join(line.split())` make sequence lines robust to whitespace.
        content = "\n>seqH\n  AG\n  \n  CT \n>seqI\n  TC\nGA"
        # seqH: "AG", "CT" -> "AGCT"
        # seqI: "TC", "GA" -> "TCGA"
        expected = [("seqH", "AGCT"), ("seqI", "TCGA")]
        self.assertEqual(from_fasta(content), expected)

    def test_from_fasta_multiple_headers_no_sequence(self):
        content = ">seq1\n>seq2\n>seq3"
        expected = [("seq1", ""), ("seq2", ""), ("seq3", "")]
        self.assertEqual(from_fasta(content), expected)

    def test_from_fasta_sequence_before_first_header(self):
        content = "ATGC\n>seq1\nCGTA"
        expected = [("seq1", "CGTA")] # "ATGC" is ignored
        self.assertEqual(from_fasta(content), expected)
        
    def test_from_fasta_only_whitespace_lines(self):
        content = "\n  \n\t\n"
        self.assertEqual(from_fasta(content), [])

    def test_from_fasta_header_with_various_chars(self):
        header = "id|123 status:active gene=XYZ; note=test data"
        content = f">{header}\nATGC"
        expected = [(header, "ATGC")]
        self.assertEqual(from_fasta(content), expected)
