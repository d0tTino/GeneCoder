import unittest
from dna_encoder import encoder

class TestBase4Encoding(unittest.TestCase):

    # Tests for encode_base4
    def test_encode_empty(self):
        self.assertEqual(encoder.encode_base4(b''), "")

    def test_encode_single_bytes(self):
        self.assertEqual(encoder.encode_base4(b'\x00'), "AAAA") # 00000000
        self.assertEqual(encoder.encode_base4(b'\x0F'), "AATT") # 00001111
        self.assertEqual(encoder.encode_base4(b'\xF0'), "TTAA") # 11110000
        self.assertEqual(encoder.encode_base4(b'\x55'), "CCCC") # 01010101
        self.assertEqual(encoder.encode_base4(b'\xAA'), "GGGG") # 10101010
        self.assertEqual(encoder.encode_base4(b'\xFF'), "TTTT") # 11111111

    def test_encode_multiple_bytes(self):
        # H = 0x48 = 01001000 -> CAGA
        # i = 0x69 = 01101001 -> CGGC
        self.assertEqual(encoder.encode_base4(b'Hi'), "CAGACGGC")
        # \x01\x23\x45\x67\x89\xAB\xCD\xEF
        # 00000001 -> AAAC
        # 00100011 -> AGAT
        # 01000101 -> CACC
        # 01100111 -> CGCT
        # 10001001 -> GACG
        # 10101011 -> GGGT
        # 11001101 -> TATC (Corrected from TCGT)
        # 11101111 -> TGTT (Corrected from TTTT)
        self.assertEqual(encoder.encode_base4(b'\x01\x23\x45\x67\x89\xAB\xCD\xEF'), "AAACAGATCACCCGCTGAGCGGGTTATCTGTT")

    # Tests for decode_base4
    def test_decode_empty(self):
        self.assertEqual(encoder.decode_base4(""), b'')

    def test_decode_simple_sequences(self):
        self.assertEqual(encoder.decode_base4("AAAA"), b'\x00')
        self.assertEqual(encoder.decode_base4("AATT"), b'\x0F')
        self.assertEqual(encoder.decode_base4("TTAA"), b'\xF0')
        self.assertEqual(encoder.decode_base4("CCCC"), b'\x55')
        self.assertEqual(encoder.decode_base4("GGGG"), b'\xAA')
        self.assertEqual(encoder.decode_base4("TTTT"), b'\xFF')

    def test_decode_multiple_bytes_sequence(self):
        self.assertEqual(encoder.decode_base4("CAGACGGC"), b'Hi')

    def test_decode_invalid_character(self):
        with self.assertRaisesRegex(ValueError, "Invalid character in DNA sequence: X"):
            encoder.decode_base4("ACGTX")
        with self.assertRaisesRegex(ValueError, "Invalid character in DNA sequence: B"):
            encoder.decode_base4("ABCG") # B is invalid
        with self.assertRaisesRegex(ValueError, "Invalid character in DNA sequence: a"):
            encoder.decode_base4("aCGT") # lowercase 'a' is invalid

    def test_decode_invalid_length(self):
        # "A" -> "00" (2 bits)
        with self.assertRaisesRegex(ValueError, "Invalid DNA sequence length for byte conversion."):
            encoder.decode_base4("A")
        # "ACA" -> "000100" (6 bits)
        with self.assertRaisesRegex(ValueError, "Invalid DNA sequence length for byte conversion."):
            encoder.decode_base4("ACA")
        # Valid characters, but not a multiple of 4 DNA chars (which means not multiple of 8 bits)
        # "AA" -> "0000" (4 bits)
        with self.assertRaisesRegex(ValueError, "Invalid DNA sequence length for byte conversion."):
            encoder.decode_base4("AA")
        # "AAA" -> "000000" (6 bits)
        with self.assertRaisesRegex(ValueError, "Invalid DNA sequence length for byte conversion."):
            encoder.decode_base4("AAA")
        # "AAAAA" -> 10 bits
        with self.assertRaisesRegex(ValueError, "Invalid DNA sequence length for byte conversion."):
            encoder.decode_base4("AAAAA")


    # Round-trip tests
    def test_roundtrip_empty(self):
        self.assertEqual(encoder.decode_base4(encoder.encode_base4(b'')), b'')

    def test_roundtrip_simple_bytes(self):
        bytes_to_test = [b'A', b'\x12', b'\x00', b'\xFF', b'\x5A', b'\xA5']
        for b_val in bytes_to_test:
            with self.subTest(byte_val=b_val):
                self.assertEqual(encoder.decode_base4(encoder.encode_base4(b_val)), b_val)

    def test_roundtrip_text(self):
        texts_to_test = [b"Hello", b"Base-4", b"DNA Encoder/Decoder Test!"]
        for text_bytes in texts_to_test:
            with self.subTest(text_bytes=text_bytes):
                self.assertEqual(encoder.decode_base4(encoder.encode_base4(text_bytes)), text_bytes)

    def test_roundtrip_longer_sequence(self):
        long_bytes = b'\xDE\xAD\xBE\xEF\xCA\xFE\xBA\xBE\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99\xAA\xBB\xCC\xDD\xEE\xFF'
        self.assertEqual(encoder.decode_base4(encoder.encode_base4(long_bytes)), long_bytes)

if __name__ == '__main__':
    unittest.main()


class TestHuffmanCoding(unittest.TestCase):

    def test_huffman_empty_input(self):
        encoded_bits, codes = encoder.encode_huffman4(b'')
        self.assertEqual(encoded_bits, "")
        self.assertEqual(codes, {})
        
        decoded_data = encoder.decode_huffman4("", {})
        self.assertEqual(decoded_data, b'')

    def test_huffman_single_symbol_input(self):
        # Test with all "00"
        data_00 = b'\x00\x00' # "00" "00" "00" "00"
        encoded_bits, codes = encoder.encode_huffman4(data_00)
        self.assertEqual(codes, {"00": "0"})
        self.assertEqual(encoded_bits, "0" * (len(data_00) * 4))
        decoded_data = encoder.decode_huffman4(encoded_bits, codes)
        self.assertEqual(decoded_data, data_00)

        # Test with all "11"
        data_ff = b'\xFF\xFF' # "11" "11" "11" "11"
        encoded_bits, codes = encoder.encode_huffman4(data_ff)
        self.assertEqual(codes, {"11": "0"})
        self.assertEqual(encoded_bits, "0" * (len(data_ff) * 4))
        decoded_data = encoder.decode_huffman4(encoded_bits, codes)
        self.assertEqual(decoded_data, data_ff)

        # Test with all "01" (using b'\x55' which is 01010101)
        data_55 = b'\x55\x55' # "01" "01" "01" "01" (repeated twice)
        encoded_bits, codes = encoder.encode_huffman4(data_55)
        self.assertEqual(codes, {"01": "0"})
        self.assertEqual(encoded_bits, "0" * (len(data_55) * 4))
        decoded_data = encoder.decode_huffman4(encoded_bits, codes)
        self.assertEqual(decoded_data, data_55)

    def test_huffman_simple_balanced_input(self):
        data = b'\x05'  # Binary 00000101 -> chunks ["00", "00", "01", "01"]
                        # Frequencies: {"00": 2, "01": 2}
        encoded_bits, codes = encoder.encode_huffman4(data)
        
        self.assertEqual(len(codes), 2)
        # Codes could be {"00": "0", "01": "1"} or {"00": "1", "01": "0"}
        self.assertTrue( ("00" in codes and "01" in codes) )
        self.assertEqual(len(codes["00"]), 1) # Each code should be 1 bit long
        self.assertEqual(len(codes["01"]), 1)
        self.assertNotEqual(codes["00"], codes["01"]) # Codes must be different

        self.assertEqual(len(encoded_bits), 4) # 4 chunks, each encoded with 1 bit
        
        decoded_data = encoder.decode_huffman4(encoded_bits, codes)
        self.assertEqual(decoded_data, data)

    def test_huffman_skewed_input(self):
        # Data: b'\x00\x00\x00\x05'
        # \x00 -> "00", "00", "00", "00"
        # \x00 -> "00", "00", "00", "00"
        # \x00 -> "00", "00", "00", "00"
        # \x05 -> "00", "00", "01", "01"
        # Frequencies: "00": 12 + 2 = 14, "01": 2
        data = b'\x00\x00\x00\x05'
        encoded_bits, codes = encoder.encode_huffman4(data)

        self.assertEqual(len(codes), 2)
        self.assertTrue( ("00" in codes and "01" in codes) )

        # The more frequent "00" should have a shorter code
        # The less frequent "01" should have a longer code (or same if only 2 symbols)
        # For 2 symbols, codes are typically '0' and '1'.
        self.assertEqual(len(codes["00"]), 1)
        self.assertEqual(len(codes["01"]), 1)
        self.assertNotEqual(codes["00"], codes["01"])
        
        # "00" appears 14 times, "01" appears 2 times. Total 16 chunks.
        # Encoded length should be 14*1 + 2*1 = 16 bits.
        self.assertEqual(len(encoded_bits), 16)

        decoded_data = encoder.decode_huffman4(encoded_bits, codes)
        self.assertEqual(decoded_data, data)

    def test_huffman_all_symbols_varied_freq(self):
        data = b'\x01\x23\x45\x67'
        # Corrected Frequencies: "00": 6, "01": 6, "10": 2, "11": 2
        # Total 16 chunks
        
        encoded_bits, codes = encoder.encode_huffman4(data)
        self.assertEqual(len(codes), 4)
        
        # Verify code lengths based on frequencies (more frequent = shorter or equal code)
        freq_map = {"00": 6, "01": 6, "10": 2, "11": 2}
        sorted_symbols_by_freq = sorted(freq_map.keys(), key=lambda s: freq_map[s], reverse=True)
        
        # Check that higher frequency symbols have codes that are shorter or equal length
        # to lower frequency symbols.
        len_s0 = len(codes[sorted_symbols_by_freq[0]]) # Freq 6 ("00" or "01")
        len_s1 = len(codes[sorted_symbols_by_freq[1]]) # Freq 6 ("00" or "01")
        len_s2 = len(codes[sorted_symbols_by_freq[2]]) # Freq 2 ("10" or "11")
        len_s3 = len(codes[sorted_symbols_by_freq[3]]) # Freq 2 ("10" or "11")

        self.assertTrue(len_s0 <= len_s2)
        self.assertTrue(len_s0 <= len_s3)
        self.assertTrue(len_s1 <= len_s2)
        self.assertTrue(len_s1 <= len_s3)

        # With frequencies 6,6,2,2, the expected codes might be:
        # "00": "00" (len 2)
        # "01": "01" (len 2)
        # "10": "10" (len 2)
        # "11": "11" (len 2)
        # Or, for example: "00": "0", "01": "10", "10": "110", "11": "111" (canonical)
        # Let's check the sum of encoded_bits length
        # Expected: 6*len(code_for_00) + 6*len(code_for_01) + 2*len(code_for_10) + 2*len(code_for_11)
        # For 6,6,2,2, a typical Huffman might give 2 bits for each.
        # e.g. 00, 01, 10, 11. Total bits = 16 * 2 = 32 bits.
        # This means no compression if all codes are 2 bits.
        # The sum of len(encoded_bits) must be less than len(data) * 4 (which is 16*2=32)
        # if there is some frequency difference that Huffman can exploit.
        # If freqs are 6,6,2,2, then codes could be '00', '01', '10', '11'. Length = 16*2 = 32.
        # Or '00': '0', '01': '10', '10': '110', '11':'111'.
        # Length = 6*1 + 6*2 + 2*3 + 2*3 = 6 + 12 + 6 + 6 = 30. This shows compression.

        self.assertTrue(len(encoded_bits) <= len(data) * 8) # Max possible length is 8 bits per byte if no compression
        self.assertTrue(len(encoded_bits) <= 16 * 3) # Max code length for 4 symbols is 3. So 16*3 = 48.
                                                    # Actually, for 4 symbols, not all can be 3. Max is N-1.
                                                    # Max total bits should be less than if all were fixed 2-bit.
                                                    # For this specific case (6,6,2,2), optimal codes are length 2 for all.
                                                    # (e.g. 00,01,10,11 if symbols are A,B,C,D)
                                                    # So expected length is 6*2 + 6*2 + 2*2 + 2*2 = 12+12+4+4 = 32 bits.
        
        # The base4 encoding would be 16 * 2 = 32 bits.
        # Huffman coding should be better or equal.
        self.assertTrue(len(encoded_bits) <= 32)


        decoded_data = encoder.decode_huffman4(encoded_bits, codes)
        self.assertEqual(decoded_data, data)

    def test_huffman_longer_text_input(self):
        data = b"This is a test string for Huffman coding."
        encoded_bits, codes = encoder.encode_huffman4(data)
        
        # Ensure some compression is happening or it's at least not worse than fixed encoding
        # Each 2-bit chunk would take 2 bits in base4. There are len(data)*4 chunks.
        # So base4 length is len(data)*4*2 = len(data)*8 bits.
        self.assertTrue(len(encoded_bits) <= len(data) * 8)

        decoded_data = encoder.decode_huffman4(encoded_bits, codes)
        self.assertEqual(decoded_data, data)

    def test_decode_huffman_invalid_sequence(self):
        # Valid codes, but encoded_bits has a trailing part not matching any code
        codes1 = {"00": "0", "01": "10", "10": "110"} # Example codes
        encoded_bits1 = "01001101" # Decodes to "00", "01", "00", "10", then "1" is left over
        with self.assertRaisesRegex(ValueError, "Invalid or truncated Huffman encoded sequence."):
            encoder.decode_huffman4(encoded_bits1, codes1)

        # Valid codes, but encoded_bits has a sequence not in the map, leaving current_code non-empty
        codes2 = {"00": "010", "01": "11"} # Note: different codes from original test
        encoded_bits2 = "0101" # Decodes "00" (from "010"), then "1" is left over
        with self.assertRaisesRegex(ValueError, "Invalid or truncated Huffman encoded sequence."):
            encoder.decode_huffman4(encoded_bits2, codes2)
            
        # Empty bits, non-empty codes (should be okay, decodes to b'')
        self.assertEqual(encoder.decode_huffman4("", codes1), b"")

    def test_decode_huffman_binary_not_multiple_of_8(self):
        codes = {"00": "0"}  # Symbol "00" is encoded as "0"
        # Encoded bits "000" decodes to three "00" symbols.
        # This means the sequence of 2-bit chunks is ["00", "00", "00"].
        # Joined, this is "000000" (6 bits). This is not a multiple of 8.
        encoded_bits = "000" 
        with self.assertRaisesRegex(ValueError, "Decoded binary string length is not a multiple of 8."):
            encoder.decode_huffman4(encoded_bits, codes)

        # Another case: codes {"00": "01", "11":"10"}
        # encoded "01100" -> "00", "11", then "0" is left (invalid sequence)
        # if encoded "0110" -> "00", "11" -> "0011" (4 bits, not multiple of 8)
        codes_multi = {"00": "01", "11":"10"}
        encoded_bits_multi = "0110" # Decodes to "00", "11" -> "0011" (4 bits)
        with self.assertRaisesRegex(ValueError, "Decoded binary string length is not a multiple of 8."):
            encoder.decode_huffman4(encoded_bits_multi, codes_multi)
            
        # Case where decoded string is empty but valid (e.g. single symbol code like "0", encoded_bits "0" * N times)
        # But resulting binary string is not multiple of 8
        # e.g. codes {"00": "0"}, encoded_bits = "0" (results in "00" -> 2 bits)
        codes_short = {"00": "0"}
        encoded_bits_short = "0" # results in "00"
        with self.assertRaisesRegex(ValueError, "Decoded binary string length is not a multiple of 8."):
            encoder.decode_huffman4(encoded_bits_short, codes_short)
            
        # Control: valid case that should pass
        # codes {"00":"0"}, encoded_bits="0000" -> four "00" -> "00000000" (8 bits) -> b'\x00'
        self.assertEqual(encoder.decode_huffman4("0000", {"00":"0"}), b'\x00')
