import sys
sys.path.insert(0, 'src') # Add src directory to Python path

import unittest
from collections import Counter
from genecoder.huffman_coding import encode_huffman, decode_huffman

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


    # Test Round-Trip Consistency
    def _assert_round_trip(self, data_bytes, msg=None):
        dna, table, pad = encode_huffman(data_bytes)
        decoded_data = decode_huffman(dna, table, pad)
        self.assertEqual(data_bytes, decoded_data, msg or f"Round trip failed for {data_bytes!r}")

    def test_round_trip_empty(self):
        self._assert_round_trip(b"")

    def test_round_trip_single_byte(self):
        self._assert_round_trip(b"A") # Test case from prompt

    def test_round_trip_repeated_bytes(self):
        self._assert_round_trip(b"BBBBBB")

    def test_round_trip_simple_string(self):
        self._assert_round_trip(b"hello world")

    def test_round_trip_varied_frequencies(self):
        self._assert_round_trip(b"aaabbc")

    def test_round_trip_all_bytes(self):
        self._assert_round_trip(bytes(range(256)))

    def test_round_trip_long_string(self):
        long_data = b"This is a longer test string with many characters and varying frequencies to robustly test Huffman coding." * 5
        self._assert_round_trip(long_data)
    
    def test_round_trip_two_chars_need_padding(self):
        # E.g. "AB", A:0, B:1 -> "01", len 2, pad 0. DNA: T
        # E.g. "AAAB", A:0, B:1 -> "0001", len 4, pad 0. DNA: AT
        # If A:0, B:10, C:11. Data "AC" -> "011". Pad 1. DNA: "0110" -> TC
        self._assert_round_trip(b"AC") # Will likely need padding for one code

    # Test decode_huffman Error Handling
    def test_decode_invalid_dna_character(self):
        # Minimal valid table for some byte, e.g., 0 -> '0'
        # This table is not from encode_huffman so care is needed.
        # encode_huffman for b"A" gives table {65:'0'}, dna "A" (from "00" after padding "0")
        dna, table, pad = encode_huffman(b"A") # dna="A", table={65:'0'}, pad=1
        self.assertRaisesRegex(ValueError, "Invalid DNA character 'X' in sequence.",
                               decode_huffman, "AGCX", table, 0) # pad 0 for simplicity here if dna is fixed

    def test_decode_invalid_padding_too_large(self):
        # dna "AA" means binary "0000". If pad is 5, it's an error.
        self.assertRaisesRegex(ValueError, "Invalid padding: 3 padding bits claimed, but only 2 bits available.",
                               decode_huffman, "A", {65: '0'}, 3) # "A" is "00", pad 3

    def test_decode_invalid_padding_non_zero_bit(self):
        # Data b"A" -> table {65:'0'}, encoded "0", padded "00", dna "A", pad 1
        # If received DNA "T" (binary "01") with pad 1, the padding bit '1' is invalid.
        table_for_A = {65: '0'} # Byte 65 ('A') maps to Huffman code '0'
        self.assertRaisesRegex(ValueError, "Invalid padding bits: expected '0's but found '1'.",
                               decode_huffman, "T", table_for_A, 1)

    def test_decode_code_not_in_table(self):
        # Encode "A", get table {65:'0'}, pad 1, dna "A" ("00")
        # If we try to decode "G" ("11") with this table, '1' or '11' is not in table.
        dna, table, pad = encode_huffman(b"A") # dna="A", table={65:'0'}, pad=1
        # "G" is "11" binary. Unpadded "1" (if pad=1). '1' is not in table { '0': 65 }
        self.assertRaisesRegex(ValueError, "Corrupted data or incorrect Huffman table: remaining unparsed bits '1'.",
                               decode_huffman, "G", table, pad)

    def test_decode_incomplete_code_at_end(self):
        # table {'A': "01", 'B': "00"}
        # dna_sequence implying "0" (e.g. "A" if pad=1)
        # This is tricky. Let's setup:
        # data = b"AB", codes could be A:0, B:1. Binary "01". DNA "T". pad 0.
        # If table is A:"00", B:"01". Data "A" -> "00". DNA "A". pad 0.
        # If we try to decode DNA "A" (binary "00") with table {"X": "001"}, "00" is not a full code.
        custom_table = {88: "001"} # 'X' -> "001"
        # DNA "A" is binary "00". This is a prefix of "001" but not the full code.
        self.assertRaisesRegex(ValueError, "Corrupted data or incorrect Huffman table: remaining unparsed bits '00'.",
                               decode_huffman, "A", custom_table, 0)


if __name__ == '__main__':
    unittest.main()
