import sys
sys.path.insert(0, 'src') # Add src directory to Python path

import unittest
from genecoder.formats import to_fasta

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
