import unittest
from dna_encoder.metrics import calculate_compression_ratio

class TestCompressionRatio(unittest.TestCase):

    def test_ratio_basic_compression(self):
        self.assertAlmostEqual(
            calculate_compression_ratio(original_size_bytes=10, encoded_payload_bits=60, huffman_table_bits=0),
            (10 * 8) / 60
        )
        self.assertAlmostEqual(
            calculate_compression_ratio(original_size_bytes=100, encoded_payload_bits=400, huffman_table_bits=100),
            (100 * 8) / (400 + 100)
        )

    def test_ratio_expansion(self):
        self.assertAlmostEqual(
            calculate_compression_ratio(original_size_bytes=10, encoded_payload_bits=100, huffman_table_bits=0),
            (10 * 8) / 100
        )

    def test_ratio_no_change(self):
        self.assertAlmostEqual(
            calculate_compression_ratio(original_size_bytes=10, encoded_payload_bits=80, huffman_table_bits=0),
            1.0
        )

    def test_ratio_with_huffman_table(self):
        self.assertAlmostEqual(
            calculate_compression_ratio(original_size_bytes=20, encoded_payload_bits=100, huffman_table_bits=20),
            (20 * 8) / (100 + 20)
        )

    def test_ratio_empty_input_zero_payload(self):
        self.assertAlmostEqual(
            calculate_compression_ratio(original_size_bytes=0, encoded_payload_bits=0, huffman_table_bits=0),
            1.0
        )

    def test_ratio_original_gt_zero_payload_zero(self):
        self.assertEqual(
            calculate_compression_ratio(original_size_bytes=10, encoded_payload_bits=0, huffman_table_bits=0),
            float('inf')
        )

    def test_ratio_type_errors(self):
        with self.assertRaises(TypeError):
            calculate_compression_ratio("10", 80, 0) # type: ignore
        with self.assertRaises(TypeError):
            calculate_compression_ratio(10, "80", 0) # type: ignore
        with self.assertRaises(TypeError):
            calculate_compression_ratio(10, 80, "0") # type: ignore
        with self.assertRaises(TypeError):
            calculate_compression_ratio(10.0, 80, 0) # type: ignore
        with self.assertRaises(TypeError):
            calculate_compression_ratio(10, 80.0, 0) # type: ignore
        with self.assertRaises(TypeError):
            calculate_compression_ratio(10, 80, 0.0) # type: ignore

    def test_ratio_value_errors(self):
        with self.assertRaises(ValueError):
            calculate_compression_ratio(-10, 80, 0)
        with self.assertRaises(ValueError):
            calculate_compression_ratio(10, -80, 0)
        with self.assertRaises(ValueError):
            calculate_compression_ratio(10, 80, -10)

    def test_ratio_floats_near_one(self):
        # (1*8)/3 = 2.666...
        self.assertAlmostEqual(
            calculate_compression_ratio(original_size_bytes=1, encoded_payload_bits=3, huffman_table_bits=0),
            8.0 / 3.0
        )
        # (1*8)/7 = 1.142857...
        self.assertAlmostEqual(
            calculate_compression_ratio(original_size_bytes=1, encoded_payload_bits=7, huffman_table_bits=0),
            8.0 / 7.0
        )
        # Example where ratio is slightly less than 1
        # (1*8)/9 = 0.888...
        self.assertAlmostEqual(
            calculate_compression_ratio(original_size_bytes=1, encoded_payload_bits=9, huffman_table_bits=0),
            8.0 / 9.0
        )

if __name__ == '__main__':
    unittest.main()
