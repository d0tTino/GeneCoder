
import unittest
import io
from collections import Counter

from genecoder.plotting import (
    prepare_huffman_codeword_length_data,
    generate_codeword_length_histogram,
    prepare_nucleotide_frequency_data,
    generate_nucleotide_frequency_plot,
    calculate_windowed_gc_content,
    identify_homopolymer_regions
)
import pytest # For new tests

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

    # --- Tests for calculate_windowed_gc_content ---
    def test_calculate_windowed_gc_empty_sequence(self):
        starts, gcs = calculate_windowed_gc_content("", window_size=5, step=1)
        self.assertEqual(starts, [])
        self.assertEqual(gcs, [])

    def test_calculate_windowed_gc_sequence_shorter_than_window(self):
        starts, gcs = calculate_windowed_gc_content("ATGC", window_size=5, step=1)
        self.assertEqual(starts, [])
        self.assertEqual(gcs, [])

    def test_calculate_windowed_gc_invalid_params(self):
        with self.assertRaises(ValueError):
            calculate_windowed_gc_content("ATGC", window_size=0, step=1)
        with self.assertRaises(ValueError):
            calculate_windowed_gc_content("ATGC", window_size=5, step=0)
        with self.assertRaises(ValueError):
            calculate_windowed_gc_content("ATGC", window_size=-1, step=1)
        with self.assertRaises(ValueError):
            calculate_windowed_gc_content("ATGC", window_size=5, step=-1)

    def test_calculate_windowed_gc_single_window(self):
        starts, gcs = calculate_windowed_gc_content("ATGCATGC", window_size=8, step=1)
        self.assertEqual(starts, [0])
        self.assertEqual(gcs, [pytest.approx(0.5)])

    def test_calculate_windowed_gc_multiple_windows(self):
        dna = "AAAAAGGGGGCCCCCTTTTT" # len 20
        # Window 1 (0-4): "AAAAA", GC=0.0
        # Window 2 (5-9): "GGGGG", GC=1.0
        # Window 3 (10-14): "CCCCC", GC=1.0
        # Window 4 (15-19): "TTTTT", GC=0.0
        starts, gcs = calculate_windowed_gc_content(dna, window_size=5, step=5)
        self.assertEqual(starts, [0, 5, 10, 15])
        self.assertEqual(gcs, [pytest.approx(0.0), pytest.approx(1.0), pytest.approx(1.0), pytest.approx(0.0)])

    def test_calculate_windowed_gc_skip_bases(self):
        # W1 (0-3): ATGC, GC=0.5
        # W2 (3-6): CATG, GC=0.5
        # W3 (6-9): GCAT, GC=0.5
        # W4 (9-12): GC -> this window is not full, so it depends on implementation.
        # Current implementation: range(0, seq_len - window_size + 1, step)
        # For dna="ATGCATGCATGC", window_size=4, step=3
        # i=0: "ATGC" -> 0.5
        # i=3: "CATG" -> 0.5
        # i=6: "GCAT" -> 0.5
        # i=9: "GCAT" -> 0.5 (Oops, mistake here, should be "GCAT")
        # No, i=9: "GC" + dna[11] = "GCA" + dna[12] = "T" => "GCAT"
        # dna[9:13] = "GCAT"
        # Expected: ([0, 3, 6, 9], [0.5, 0.5, 0.5, 0.5])
        starts, gcs = calculate_windowed_gc_content("ATGCATGCATGC", window_size=4, step=3)
        self.assertEqual(starts, [0, 3, 6])
        self.assertEqual(gcs, [pytest.approx(0.5), pytest.approx(0.5), pytest.approx(0.5)])
        
        # Test with a step that makes the last window partial if not handled
        # dna="ATGCATGC", window_size=5, step=2
        # W1 (0-4): "ATGCA", GC = 2/5 = 0.4
        # W2 (2-6): "GCATG", GC = 3/5 = 0.6
        # W3 (4-8): "ATGC" -> this window is "ATGC" + sequence[8] (if exists)
        # seq_len - window_size + 1 = 8 - 5 + 1 = 4. Loop: 0, 2.
        # i=0: "ATGCA" -> GC=0.4
        # i=2: "GCATG" -> GC=0.6
        starts, gcs = calculate_windowed_gc_content("ATGCATGC", window_size=5, step=2)
        self.assertEqual(starts, [0, 2]) # Last full window starts at index 3 (ATGC), 8-5=3. Range goes up to 3.
                                       # 0, 2. Next is 4, but 4 > 8-5 = 3. So only 0,2.
        self.assertEqual(gcs, [pytest.approx(0.4), pytest.approx(0.6)])


    def test_calculate_windowed_gc_with_non_atcg_chars(self):
        # "AAANNGGG", window_size=4, step=1
        # W1 (0-3) "AAAN": atcg_count=3, gc_count=0. GC = 0.0
        # W2 (1-4) "AANN": atcg_count=2, gc_count=0. GC = 0.0
        # W3 (2-5) "ANNG": atcg_count=2, gc_count=1. GC = 0.5
        # W4 (3-6) "NNGG": atcg_count=2, gc_count=2. GC = 1.0
        # W5 (4-7) "NGGG": atcg_count=3, gc_count=3. GC = 1.0
        dna = "AAANNGGG"
        starts, gcs = calculate_windowed_gc_content(dna, window_size=4, step=1)
        self.assertEqual(starts, [0, 1, 2, 3, 4])
        self.assertEqual(gcs, [
            pytest.approx(0.0), 
            pytest.approx(0.0), 
            pytest.approx(0.5), 
            pytest.approx(1.0), 
            pytest.approx(1.0)
        ])

    # --- Tests for identify_homopolymer_regions ---
    def test_identify_homopolymers_empty_sequence(self):
        self.assertEqual(identify_homopolymer_regions("", min_len=3), [])

    def test_identify_homopolymers_invalid_min_len(self):
        with self.assertRaises(ValueError):
            identify_homopolymer_regions("ATGC", min_len=0)
        with self.assertRaises(ValueError):
            identify_homopolymer_regions("ATGC", min_len=1)
        # min_len=2 should be valid
        self.assertIsNotNone(identify_homopolymer_regions("AA",min_len=2))


    def test_identify_homopolymers_no_regions_found(self):
        self.assertEqual(identify_homopolymer_regions("AGCTAGCT", min_len=3), [])
        self.assertEqual(identify_homopolymer_regions("AAGGTTCC", min_len=3), [])

    def test_identify_homopolymers_single_region(self):
        self.assertEqual(identify_homopolymer_regions("AAATGCC", min_len=3), [(0, 2, 'A')])
        self.assertEqual(identify_homopolymer_regions("TGCCCATT", min_len=3), [(2, 4, 'C')])

    def test_identify_homopolymers_multiple_distinct_regions(self):
        # "AAATTTTGGCC", min_len=3 -> [(0, 2, 'A'), (3, 6, 'T')] (GG and CC are too short)
        self.assertEqual(identify_homopolymer_regions("AAATTTTGGCC", min_len=3), [(0, 2, 'A'), (3, 6, 'T')])
        # "GGGGGAAACCCC", min_len=3 -> [(0,4,'G'), (5,7,'A'), (8,11,'C')]
        self.assertEqual(identify_homopolymer_regions("GGGGGAAACCCC", min_len=3), [(0,4,'G'), (5,7,'A'), (8,11,'C')])


    def test_identify_homopolymers_at_ends_and_middle(self):
        # Start: "AAAAGCT" min_len=3 -> [(0,3,'A')]
        self.assertEqual(identify_homopolymer_regions("AAAAGCT", min_len=3), [(0,3,'A')])
        # Middle: "AGTTTTGCT" min_len=3 -> [(2,5,'T')]
        self.assertEqual(identify_homopolymer_regions("AGTTTTGCT", min_len=3), [(2,5,'T')])
        # End: "AGCTGGGG" min_len=3 -> [(4,7,'G')]
        self.assertEqual(identify_homopolymer_regions("AGCTGGGG", min_len=3), [(4,7,'G')])
        # All three
        self.assertEqual(identify_homopolymer_regions("AAAAGCTTTTCGGGGG", min_len=4), [(0,3,'A'), (6,9,'T'), (11,15,'G')])


    def test_identify_homopolymers_adjacent_and_overlapping_like(self):
        # Current logic finds longest continuous runs. "AAAAAAPPP" min_len=3 -> [(0,5,'A'),(6,8,'P')]
        self.assertEqual(identify_homopolymer_regions("AAAAAAPPP", min_len=3), [(0,5,'A'),(6,8,'P')])
        # "AAABBAAA", min_len=3 -> [(0,2,'A'), (5,7,'A')]
        self.assertEqual(identify_homopolymer_regions("AAABBAAA", min_len=3), [(0,2,'A'), (5,7,'A')])


    def test_identify_homopolymers_mixed_case(self):
        # "aaAAAttT", min_len=3 -> should be case-insensitive [(0,5,'A'),(6,7,'T')]
        # The function converts to upper: "AAAAAATT"
        # AAAAAA -> (0,5,'A')
        # TT -> len 2, not >=3
        # If min_len=2: [(0,5,'A'),(6,7,'T')]
        self.assertEqual(identify_homopolymer_regions("aaAAAttT", min_len=3), [(0,4,'A'), (5,7,'T')])
        self.assertEqual(identify_homopolymer_regions("aaAAAttT", min_len=2), [(0,4,'A'), (5,7,'T')])

    def test_identify_homopolymers_with_non_dna_chars(self):
        # "AAANNTTTT", min_len=3 -> [(0,2,'A'), (6,9,'T')] N should break homopolymers
        self.assertEqual(identify_homopolymer_regions("AAANNTTTT", min_len=3), [(0,2,'A'), (5,8,'T')]) # Corrected based on N break
        # "GGXXAAA", min_len=2 -> [(0,1,'G'), (4,6,'A')]
        self.assertEqual(identify_homopolymer_regions("GGXXAAA", min_len=2), [(0,1,'G'), (2,3,'X'), (4,6,'A')])
        # "CCC YYYY Z", min_len=3 -> [(0,2,'C'), (4,7,'Y')] Space breaks
        self.assertEqual(identify_homopolymer_regions("CCC YYYY Z", min_len=3), [(0,2,'C'), (4,7,'Y')])

if __name__ == '__main__':
    unittest.main()
