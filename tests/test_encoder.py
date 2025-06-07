import unittest


import genecoder.encoders as encoder  # noqa: E402

class TestBase4Encoding(unittest.TestCase):

    # Tests for encode_base4_direct
    def test_encode_empty(self):
        self.assertEqual(encoder.encode_base4_direct(b''), "")

    def test_encode_single_bytes(self):
        self.assertEqual(encoder.encode_base4_direct(b'\x00'), "AAAA") # 00000000
        self.assertEqual(encoder.encode_base4_direct(b'\x0F'), "AATT") # 00001111
        self.assertEqual(encoder.encode_base4_direct(b'\xF0'), "TTAA") # 11110000
        self.assertEqual(encoder.encode_base4_direct(b'\x55'), "CCCC") # 01010101
        self.assertEqual(encoder.encode_base4_direct(b'\xAA'), "GGGG") # 10101010
        self.assertEqual(encoder.encode_base4_direct(b'\xFF'), "TTTT") # 11111111

    def test_encode_multiple_bytes(self):
        # H = 0x48 = 01001000 -> CAGA
        # i = 0x69 = 01101001 -> CGGC
        self.assertEqual(encoder.encode_base4_direct(b'Hi'), "CAGACGGC")
        # \x01\x23\x45\x67\x89\xAB\xCD\xEF
        # 00000001 -> AAAC
        # 00100011 -> AGAT
        # 01000101 -> CACC
        # 01100111 -> CGCT
        # 10001001 -> GACG
        # 10101011 -> GGGT
        # 11001101 -> TATC (Corrected from TCGT)
        # 11101111 -> TGTT (Corrected from TTTT)
        self.assertEqual(encoder.encode_base4_direct(b'\x01\x23\x45\x67\x89\xAB\xCD\xEF'), "AAACAGATCACCCGCTGAGCGGGTTATCTGTT")

    # Tests for decode_base4_direct
    def test_decode_empty(self):
        self.assertEqual(encoder.decode_base4_direct("")[0], b'')

    def test_decode_simple_sequences(self):
        self.assertEqual(encoder.decode_base4_direct("AAAA")[0], b'\x00')
        self.assertEqual(encoder.decode_base4_direct("AATT")[0], b'\x0F')
        self.assertEqual(encoder.decode_base4_direct("TTAA")[0], b'\xF0')
        self.assertEqual(encoder.decode_base4_direct("CCCC")[0], b'\x55')
        self.assertEqual(encoder.decode_base4_direct("GGGG")[0], b'\xAA')
        self.assertEqual(encoder.decode_base4_direct("TTTT")[0], b'\xFF')

    def test_decode_multiple_bytes_sequence(self):
        self.assertEqual(encoder.decode_base4_direct("CAGACGGC")[0], b'Hi')

    def test_decode_invalid_character(self):
        with self.assertRaisesRegex(ValueError, "Invalid character in sequence to decode"):
            encoder.decode_base4_direct("ACGTX")
        with self.assertRaisesRegex(ValueError, "Invalid character in sequence to decode"):
            encoder.decode_base4_direct("ABCG") # B is invalid
        with self.assertRaisesRegex(ValueError, "Invalid character in sequence to decode"):
            encoder.decode_base4_direct("aCGT") # lowercase 'a' is invalid

    def test_decode_invalid_length(self):
        # "A" -> "00" (2 bits)
        with self.assertRaisesRegex(ValueError, "Length of sequence to decode must be a multiple of 4"):
            encoder.decode_base4_direct("A")
        # "ACA" -> "000100" (6 bits)
        with self.assertRaisesRegex(ValueError, "Length of sequence to decode must be a multiple of 4"):
            encoder.decode_base4_direct("ACA")
        # Valid characters, but not a multiple of 4 DNA chars (which means not multiple of 8 bits)
        # "AA" -> "0000" (4 bits)
        with self.assertRaisesRegex(ValueError, "Length of sequence to decode must be a multiple of 4"):
            encoder.decode_base4_direct("AA")
        # "AAA" -> "000000" (6 bits)
        with self.assertRaisesRegex(ValueError, "Length of sequence to decode must be a multiple of 4"):
            encoder.decode_base4_direct("AAA")
        # "AAAAA" -> 10 bits
        with self.assertRaisesRegex(ValueError, "Length of sequence to decode must be a multiple of 4"):
            encoder.decode_base4_direct("AAAAA")


    # Round-trip tests
    def test_roundtrip_empty(self):
        self.assertEqual(
            encoder.decode_base4_direct(encoder.encode_base4_direct(b''))[0],
            b'',
        )

    def test_roundtrip_simple_bytes(self):
        bytes_to_test = [b'A', b'\x12', b'\x00', b'\xFF', b'\x5A', b'\xA5']
        for b_val in bytes_to_test:
            with self.subTest(byte_val=b_val):
                self.assertEqual(
                    encoder.decode_base4_direct(encoder.encode_base4_direct(b_val))[0],
                    b_val,
                )

    def test_roundtrip_text(self):
        texts_to_test = [b"Hello", b"Base-4", b"DNA Encoder/Decoder Test!"]
        for text_bytes in texts_to_test:
            with self.subTest(text_bytes=text_bytes):
                self.assertEqual(
                    encoder.decode_base4_direct(encoder.encode_base4_direct(text_bytes))[0],
                    text_bytes,
                )

    def test_roundtrip_longer_sequence(self):
        long_bytes = b'\xDE\xAD\xBE\xEF\xCA\xFE\xBA\xBE\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99\xAA\xBB\xCC\xDD\xEE\xFF'
        self.assertEqual(
            encoder.decode_base4_direct(encoder.encode_base4_direct(long_bytes))[0],
            long_bytes,
        )

if __name__ == '__main__':
    unittest.main()
