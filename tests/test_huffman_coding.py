import unittest
# collections.Counter is not directly used in these tests, but it's fundamental
# to the huffman_coding module itself. Keep if needed for other tests, or remove if strictly not used.
# from collections import Counter 
from genecoder.huffman_coding import encode_huffman, decode_huffman
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T

class TestHuffmanCoding(unittest.TestCase):

    # Test encode_huffman
    def test_encode_empty(self):
        self.assertEqual(encode_huffman(b""), ("", {}, 0))

    def test_encode_single_unique_byte(self):
        data = b"AAAAA"
        # Expected table: {65: '0'}. The code '0' is standard for a single symbol.
        # Encoded binary string: "00000" (5 times '0').
        # Padding: num_padding_bits = 1 (to make "000000").
        # DNA sequence: "AAA" (from "000000").
        dna, table, pad = encode_huffman(data)
        self.assertEqual(table, {65: '0'})
        self.assertEqual(pad, 1) # "00000" -> "000000"
        self.assertEqual(dna, "AAA") # "00" "00" "00"

    def test_encode_simple_string_properties(self):
        data = b"aabbc" # Frequencies: a:2, b:2, c:1
        dna, table, pad = encode_huffman(data)

        # Verify table properties
        self.assertEqual(len(table), 3) # Should have codes for 'a', 'b', 'c'
        self.assertIn(ord('a'), table)
        self.assertIn(ord('b'), table)
        self.assertIn(ord('c'), table)

        # Verify code lengths (c should be shorter or equal, a and b potentially longer or equal)
        # A possible table: c: '0', a: '10', b: '11'. Lengths: c=1, a=2, b=2
        # Another: a: '0', b: '10', c: '11'. Lengths: a=1, b=2, c=2
        # The shortest code should belong to the least frequent or one of the least frequent if tie.
        # The longest codes should belong to the most frequent or one of the most frequent if tie.
        # This is a bit complex to assert directly due to Huffman variations.
        # Round-trip test is more important for overall correctness.

        # Verify binary string properties
        expected_binary_len = 0
        for byte_val in data:
            expected_binary_len += len(table[byte_val])
        
        self.assertIn(pad, [0, 1]) # Padding should be 0 or 1
        expected_padded_len = expected_binary_len + pad
        self.assertEqual(expected_padded_len % 2, 0)
        
        # Verify DNA sequence length
        self.assertEqual(len(dna) * 2, expected_padded_len)


    def test_encode_needs_padding(self):
        # Example: data = b"ab", table might be a:'0', b:'1'
        # Binary: "01", no padding needed, pad=0, DNA "T"
        # Example: data = b"abc", table might be a:'00', b:'01', c:'1'
        # Binary "00011", needs 1 padding bit: "000110"
        # DNA: "ATC"
        data = b"abc" # Freq: a:1, b:1, c:1
                      # Possible table: a:00, b:01, c:10 -> no, this is not prefix free if c is '1'
                      # More likely: a:0, b:10, c:11. Binary: 01011. Pad=1. DNA: ATCG (01 01 10 -> 010110)
                      # Let's use a clearer example:
        data = b"abb" # a:1, b:2. Possible: a:'0', b:'1'. Binary: "011". Pad=1. Result: "0110" -> "TC"
        dna, table, pad = encode_huffman(data)
        
        binary_str = "".join(table[byte_val] for byte_val in data)
        if len(binary_str) % 2 != 0:
            self.assertEqual(pad, 1)
        else:
            self.assertEqual(pad, 0)
        self.assertEqual(len(dna) * 2, len(binary_str) + pad)


    # Test Round-Trip Consistency (No Parity)
    def _assert_round_trip_no_parity(self, data_bytes, msg=None):
        # Test without parity first
        dna_no_parity, table_no_parity, pad_no_parity = encode_huffman(data_bytes, add_parity=False)
        decoded_data_no_parity, errors_no_parity = decode_huffman(
            dna_no_parity, table_no_parity, pad_no_parity, check_parity=False
        )
        self.assertEqual(data_bytes, decoded_data_no_parity, msg or f"Round trip (no parity) failed for {data_bytes!r}")
        self.assertEqual(errors_no_parity, [], "Errors should be empty for no_parity round trip")

    def test_round_trip_empty(self):
        # Renamed from test_round_trip_empty to avoid conflict if we add a parity version
        self._assert_round_trip_no_parity(b"")
        self._assert_round_trip(b"")

    def test_round_trip_single_byte(self):
        self._assert_round_trip_no_parity(b"A")

    def test_round_trip_repeated_bytes(self):
        self._assert_round_trip_no_parity(b"BBBBBB")

    def test_round_trip_simple_string(self):
        self._assert_round_trip_no_parity(b"hello world")

    def test_round_trip_varied_frequencies(self):
        self._assert_round_trip_no_parity(b"aaabbc")

    def test_round_trip_all_bytes(self):
        self._assert_round_trip_no_parity(bytes(range(256)))

    def test_round_trip_long_string(self):
        long_data = b"This is a longer test string with many characters and varying frequencies to robustly test Huffman coding." * 5
        self._assert_round_trip_no_parity(long_data)
    
    def test_round_trip_two_chars_need_padding(self):
        self._assert_round_trip_no_parity(b"AC")

    # Test decode_huffman Error Handling (No Parity Check context)
    def test_decode_invalid_dna_character(self):
        dna_no_parity, table_no_parity, pad_no_parity = encode_huffman(b"A", add_parity=False)
        with self.assertRaisesRegex(ValueError, "Invalid DNA character 'X' in sequence."):
            decode_huffman("AGCX", table_no_parity, pad_no_parity, check_parity=False)

    def test_decode_invalid_padding_too_large(self):
        with self.assertRaisesRegex(ValueError, "Invalid padding: 3 padding bits claimed, but only 2 bits available."):
            decode_huffman("A", {65: '0'}, 3, check_parity=False)

    def test_decode_invalid_padding_non_zero_bit(self):
        table_for_A = {65: '0'} 
        with self.assertRaisesRegex(ValueError, "Invalid padding bits: expected '0's but found '1'."):
            decode_huffman("T", table_for_A, 1, check_parity=False)

    def test_decode_code_not_in_table(self):
        dna_no_parity, table_no_parity, pad_no_parity = encode_huffman(b"A", add_parity=False)
        with self.assertRaisesRegex(ValueError, "Invalid padding bits: expected all '0's but found '1'."):
            decode_huffman("G", table_no_parity, pad_no_parity, check_parity=False)  # "G" is "11", unpadded "1"

    def test_decode_incomplete_code_at_end(self):
        custom_table = {ord('X'): "001"} 
        with self.assertRaisesRegex(ValueError, "Corrupted data or incorrect Huffman table: remaining unparsed bits '00'."):
            decode_huffman("A", custom_table, 0, check_parity=False) # "A" is "00"

    # --- Tests for Huffman with Parity ---
    def test_encode_huffman_with_parity(self):
        data = b"aabbc" # Freq: a:2, b:2, c:1
        k_val = 4
        dna_no_parity, _, _ = encode_huffman(data, add_parity=False)
        dna_with_parity, _, _ = encode_huffman(data, add_parity=True, k_value=k_val, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T)
        
        # Expected length increase: for each k_val block of original DNA, one parity bit is added.
        expected_parity_bits = (len(dna_no_parity) + k_val - 1) // k_val if dna_no_parity else 0
        self.assertEqual(len(dna_with_parity), len(dna_no_parity) + expected_parity_bits)
        # Further structural checks could be done, but exact match is hard due to Huffman table variations.

    def test_decode_huffman_with_parity_no_errors(self):
        data = b"hello"
        k_val = 3
        dna_with_parity, table, pad = encode_huffman(
            data, add_parity=True, k_value=k_val, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
        )
        decoded_data, errors = decode_huffman(
            dna_with_parity, table, pad, check_parity=True, k_value=k_val, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
        )
        self.assertEqual(decoded_data, data)
        self.assertEqual(errors, [])

    def test_decode_huffman_with_parity_with_errors(self):
        data = b"worlddata"
        k_val = 3
        dna_with_parity, table, pad = encode_huffman(
            data, add_parity=True, k_value=k_val, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
        )
        
        # Corrupt a parity bit (e.g., the first one at index k_val)
        if len(dna_with_parity) > k_val:
            original_char = dna_with_parity[k_val]
            corrupted_char = 'A' if original_char != 'A' else 'T' # Flip it
            corrupted_dna = dna_with_parity[:k_val] + corrupted_char + dna_with_parity[k_val+1:]
            
            decoded_data, errors = decode_huffman(
                corrupted_dna, table, pad, check_parity=True, k_value=k_val, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
            )
            self.assertEqual(decoded_data, data, "Data should still decode correctly")
            self.assertIn(0, errors, "Error should be detected in the first block")
        else:
            self.skipTest("DNA sequence too short to corrupt a parity bit meaningfully.")

    def _assert_round_trip_with_parity(self, data_bytes, k_value, msg=None):
        dna, table, pad = encode_huffman(
            data_bytes, add_parity=True, k_value=k_value, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
        )
        decoded_data, errors = decode_huffman(
            dna, table, pad, check_parity=True, k_value=k_value, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
        )
        self.assertEqual(data_bytes, decoded_data, msg or f"Round trip (with parity, k={k_value}) failed for {data_bytes!r}")
        self.assertEqual(errors, [], f"No errors expected for clean round trip (with parity, k={k_value}) for {data_bytes!r}")

    def test_round_trip_huffman_with_parity_various_k(self):
        self._assert_round_trip_with_parity(b"Parity test for Huffman!", k_value=3)
        self._assert_round_trip_with_parity(b"Another example with different k.", k_value=5)
        self._assert_round_trip_with_parity(b"Short", k_value=2) # Test with small k
        self._assert_round_trip_with_parity(b"", k_value=3) # Empty string
        self._assert_round_trip_with_parity(b"X", k_value=1) # Single byte, small k


if __name__ == '__main__':
    unittest.main()
