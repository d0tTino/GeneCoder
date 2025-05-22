import sys
import os
# Add src directory to Python path for module import
# This assumes the tests are run from the project root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import unittest
import io
from collections import Counter

from genecoder.plotting import (
    prepare_huffman_codeword_length_data,
    generate_codeword_length_histogram,
    prepare_nucleotide_frequency_data,
    generate_nucleotide_frequency_plot
)

class TestPlotting(unittest.TestCase):

    # Tests for Huffman Codeword Length Histogram
    def test_prepare_huffman_data_empty_table(self):
        self.assertEqual(prepare_huffman_codeword_length_data({}), Counter())

    def test_prepare_huffman_data_simple_table(self):
        table = {65: "0", 66: "10", 67: "110"} # A:1, B:2, C:3 bits
        expected = Counter({1: 1, 2: 1, 3: 1})
        self.assertEqual(prepare_huffman_codeword_length_data(table), expected)

    def test_generate_histogram_empty_data(self):
        buf = generate_codeword_length_histogram(Counter())
        self.assertIsInstance(buf, io.BytesIO)
        self.assertTrue(len(buf.getvalue()) > 0, "Buffer should not be empty, even for 'No data' plot.")
        self.assertTrue(buf.getvalue().startswith(b'\x89PNG\r\n\x1a\n'), "Output is not a PNG image.")
        buf.close()

    def test_generate_histogram_simple_data(self):
        counts = Counter({3: 5, 4: 2})
        buf = generate_codeword_length_histogram(counts)
        self.assertIsInstance(buf, io.BytesIO)
        self.assertTrue(len(buf.getvalue()) > 0)
        self.assertTrue(buf.getvalue().startswith(b'\x89PNG\r\n\x1a\n'), "Output is not a PNG image.")
        buf.close()

    # Tests for Nucleotide Frequency Distribution
    def test_prepare_nucleotide_data_empty_sequence(self):
        expected = Counter({'A':0, 'T':0, 'C':0, 'G':0})
        self.assertEqual(prepare_nucleotide_frequency_data(""), expected)

    def test_prepare_nucleotide_data_simple_sequence(self):
        dna = "AATTCG"
        expected = Counter({'A':2, 'T':2, 'C':1, 'G':1})
        self.assertEqual(prepare_nucleotide_frequency_data(dna), expected)

    def test_prepare_nucleotide_data_with_invalid_chars(self):
        dna = "AATXTCGY" # X, Y should be ignored
        expected = Counter({'A':2, 'T':2, 'C':1, 'G':1})
        self.assertEqual(prepare_nucleotide_frequency_data(dna), expected)

    def test_prepare_nucleotide_data_only_some_nts(self):
        dna = "AAAA"
        expected = Counter({'A':4, 'T':0, 'C':0, 'G':0})
        self.assertEqual(prepare_nucleotide_frequency_data(dna), expected)

    def test_generate_frequency_plot_empty_data(self):
        # Test with a Counter that explicitly has all nucleotides as 0
        buf = generate_nucleotide_frequency_plot(Counter({'A':0, 'T':0, 'C':0, 'G':0}))
        self.assertIsInstance(buf, io.BytesIO)
        self.assertTrue(len(buf.getvalue()) > 0, "Buffer should not be empty, even for 'No data' plot.")
        self.assertTrue(buf.getvalue().startswith(b'\x89PNG\r\n\x1a\n'), "Output is not a PNG image.")
        buf.close()
        
        # Test with a completely empty Counter
        buf_empty_counter = generate_nucleotide_frequency_plot(Counter())
        self.assertIsInstance(buf_empty_counter, io.BytesIO)
        self.assertTrue(len(buf_empty_counter.getvalue()) > 0, "Buffer for empty Counter should also show 'No data'.")
        self.assertTrue(buf_empty_counter.getvalue().startswith(b'\x89PNG\r\n\x1a\n'), "Output is not a PNG image.")
        buf_empty_counter.close()


    def test_generate_frequency_plot_simple_data(self):
        counts = Counter({'A':10, 'T':5, 'C':5, 'G':10})
        buf = generate_nucleotide_frequency_plot(counts)
        self.assertIsInstance(buf, io.BytesIO)
        self.assertTrue(len(buf.getvalue()) > 0)
        self.assertTrue(buf.getvalue().startswith(b'\x89PNG\r\n\x1a\n'), "Output is not a PNG image.")
        buf.close()

if __name__ == '__main__':
    unittest.main()
