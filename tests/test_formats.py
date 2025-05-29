import unittest
from dna_encoder.formats import to_fasta

class TestFastaFormatting(unittest.TestCase):

    def test_fasta_empty_sequence(self):
        self.assertEqual(
            to_fasta(dna_sequence="", header="empty_header", line_length=60),
            ">empty_header\n"
        )

    def test_fasta_short_sequence_no_wrapping(self):
        self.assertEqual(
            to_fasta(dna_sequence="ACGT", header="short_seq", line_length=60),
            ">short_seq\nACGT\n"
        )

    def test_fasta_sequence_exact_line_length(self):
        self.assertEqual(
            to_fasta(dna_sequence="ACGTACGT", header="exact_len", line_length=8),
            ">exact_len\nACGTACGT\n"
        )

    def test_fasta_sequence_requires_wrapping(self):
        expected_output = (
            ">wrap_me\n"
            "ABCDEFGHIJ\n"
            "KLMNOPQRST\n"
            "UVWXYZ\n"
        )
        self.assertEqual(
            to_fasta(dna_sequence="ABCDEFGHIJKLMNOPQRSTUVWXYZ", header="wrap_me", line_length=10),
            expected_output
        )

    def test_fasta_sequence_wrapping_last_line_partial(self):
        expected_output = (
            ">partial_last\n"
            "ACGT\n"
            "ACGT\n"
            "ACG\n"
        )
        self.assertEqual(
            to_fasta(dna_sequence="ACGTACGTACG", header="partial_last", line_length=4),
            expected_output
        )

    def test_fasta_custom_line_length(self):
        expected_output = (
            ">custom_len\n"
            "ACGTA\n"
            "CGTAC\n"
            "GTACG\n"
            "T\n"
        )
        self.assertEqual(
            to_fasta(dna_sequence="ACGTACGTACGTACGT", header="custom_len", line_length=5),
            expected_output
        )

    def test_fasta_line_length_zero_or_negative(self):
        self.assertEqual(
            to_fasta(dna_sequence="ACGTACGT", header="no_wrap_zero", line_length=0),
            ">no_wrap_zero\nACGTACGT\n"
        )
        self.assertEqual(
            to_fasta(dna_sequence="ACGTACGT", header="no_wrap_neg", line_length=-5),
            ">no_wrap_neg\nACGTACGT\n"
        )

    def test_fasta_header_only(self):
        # This is effectively the same as test_fasta_empty_sequence
        self.assertEqual(
            to_fasta(dna_sequence="", header="header_only"), # Using default line_length
            ">header_only\n"
        )

    def test_fasta_long_header(self):
        header_content = "This is a very long header string with spaces and symbols !@#$%^&*()"
        self.assertEqual(
            to_fasta(dna_sequence="ACGT", header=header_content),
            f">{header_content}\nACGT\n"
        )

if __name__ == '__main__':
    unittest.main()
