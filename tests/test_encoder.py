import unittest
import os
import sys

SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from dna_encoder import encoder  # noqa: E402

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
