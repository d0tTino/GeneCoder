import sys
sys.path.insert(0, 'src') # Add src directory to Python path for module import

import unittest
from genecoder.encoders import encode_base4_direct, decode_base4_direct

class TestBase4DirectMapping(unittest.TestCase):

    # Tests for encode_base4_direct
    def test_encode_empty(self):
        self.assertEqual(encode_base4_direct(b''), "")

    def test_encode_single_byte_zero(self):
        # 0b00000000 -> AAAA
        self.assertEqual(encode_base4_direct(b'\x00'), "AAAA")

    def test_encode_single_byte_max(self):
        # 0b11111111 -> GGGG
        self.assertEqual(encode_base4_direct(b'\xff'), "GGGG")

    def test_encode_ascii_char(self):
        # 'A' (ASCII 65) is 0b01000001
        # 01 -> T
        # 00 -> A
        # 00 -> A
        # 01 -> T
        # Expected: TAAT (Correction: The prompt example says "ATAA", let's re-verify. 01000001 -> 01 00 00 01 -> T A A T. The prompt image has 00->A, 01->T, 10->C, 11->G. So 01->T, 00->A, 00->A, 01->T is "TAAT". I will use "TAAT" as per the mapping logic.)
        # The prompt example had 'A' (01000001) -> "ATAA". Let's check that.
        # 01 (T) 00 (A) 00 (A) 01 (T) -> "TAAT"
        # If "ATAA" is expected for 'A' (01000001):
        # A (00) T (01) A (00) A (00) -> 00010000. This is not 65.
        # The prompt description for encode_base4_direct states:
        # 1st pair: (byte >> 6) & 0b11
        # 2nd pair: (byte >> 4) & 0b11
        # 3rd pair: (byte >> 2) & 0b11
        # 4th pair: (byte >> 0) & 0b11
        # For byte 'A' = 0b01000001:
        # 1st pair: (01000001 >> 6) & 0b11 = 0b01 & 0b11 = 0b01 -> T
        # 2nd pair: (01000001 >> 4) & 0b11 = 0b0100 & 0b11 = 0b00 -> A
        # 3rd pair: (01000001 >> 2) & 0b11 = 0b010000 & 0b11 = 0b00 -> A
        # 4th pair: (01000001 >> 0) & 0b11 = 0b01000001 & 0b11 = 0b01 -> T
        # So, b'A' (01000001) should indeed be "TAAT". I will use this. The example "ATAA" in the prompt might be a typo.
        self.assertEqual(encode_base4_direct(b'A'), "TAAT")


    def test_encode_multiple_bytes(self):
        # 'H' (ASCII 72) is 0b01001000
        # 01 -> T
        # 00 -> A
        # 10 -> C
        # 00 -> A
        # Result: "TACA"
        # 'i' (ASCII 105) is 0b01101001
        # 01 -> T
        # 10 -> C
        # 10 -> C
        # 01 -> T
        # Result: "TCCT"
        # Expected for "Hi": "TACATCCT"
        # The prompt example is "ATCAATTG". Let's verify this.
        # 'H' = 01001000. If "ATCA":
        # A (00) T (01) C (10) A (00) -> 00011000 (Decimal 24). This is not 'H' (72).
        # Using the defined mapping:
        # H (01001000): 01(T) 00(A) 10(C) 00(A) -> "TACA"
        # i (01101001): 01(T) 10(C) 10(C) 01(T) -> "TCCT"
        # So "Hi" -> "TACATCCT". I will use this.
        self.assertEqual(encode_base4_direct(b'Hi'), "TACATCCT")

    def test_encode_byte_sequence(self):
        # \x12 -> 00010010 -> A(00)A(00)T(01)C(10) -> AATC (Corrected from prompt's AATA)
        # \x34 -> 00110100 -> A(00)C(10)T(01)A(00) -> ACTA (Corrected from prompt's ACTA)
        # \xAB -> 10101011 -> C(10)G(11)C(10)G(11) -> CGCG (Corrected from prompt's CGTG)
        # \xCD -> 11001101 -> G(11)A(00)G(11)T(01) -> GAGT (Corrected from prompt's GCGT)
        # Expected: "AATCACTACGCGGAGT"
        # The prompt example: "AATAACTACGTGCGTG"
        # Let's re-calculate based on the implemented encoder:
        # \x12 (00010010): (00)(A) (01)(T) (00)(A) (10)(C) -> "ATAC"
        # \x34 (00110100): (00)(A) (11)(G) (01)(T) (00)(A) -> "AGTA"
        # \xAB (10101011): (10)(C) (10)(C) (10)(C) (11)(G) -> "CCCG"
        # \xCD (11001101): (11)(G) (00)(A) (11)(G) (01)(T) -> "GAGT"
        # Expected: "ATACAGTACCCGGAGT"
        self.assertEqual(encode_base4_direct(b'\x12\x34\xAB\xCD'), "ATACAGTACCCGGAGT")

    # Tests for decode_base4_direct
    def test_decode_empty(self):
        self.assertEqual(decode_base4_direct(""), b'')

    def test_decode_valid_sequence_aaaa(self):
        self.assertEqual(decode_base4_direct("AAAA"), b'\x00')

    def test_decode_valid_sequence_gggg(self):
        self.assertEqual(decode_base4_direct("GGGG"), b'\xff')

    def test_decode_ascii_char_reverse(self):
        # Corresponds to b'A' (01000001) which encodes to "TAAT"
        self.assertEqual(decode_base4_direct("TAAT"), b'A')

    def test_decode_multiple_bytes_reverse(self):
        # Corresponds to b'Hi' which encodes to "TACATCCT"
        self.assertEqual(decode_base4_direct("TACATCCT"), b'Hi')

    def test_decode_byte_sequence_reverse(self):
        # Corresponds to b'\x12\x34\xAB\xCD' which encodes to "ATACAGTACCCGGAGT"
        self.assertEqual(decode_base4_direct("ATACAGTACCCGGAGT"), b'\x12\x34\xAB\xCD')

    # Test encode-decode consistency (round trip)
    def test_round_trip_empty(self):
        data = b''
        self.assertEqual(decode_base4_direct(encode_base4_direct(data)), data)

    def test_round_trip_simple_string(self):
        data = b'Hello GeneCoder!'
        self.assertEqual(decode_base4_direct(encode_base4_direct(data)), data)

    def test_round_trip_various_bytes(self):
        data = b'\x00\x01\xFA\x80\x7F\xff' # Added \xff for completeness
        self.assertEqual(decode_base4_direct(encode_base4_direct(data)), data)

    # Test decode_base4_direct error handling
    def test_decode_invalid_character(self):
        with self.assertRaises(ValueError):
            decode_base4_direct("AGCX") # X is invalid

    def test_decode_invalid_character_lowercase(self):
        with self.assertRaises(ValueError):
            decode_base4_direct("agct") # lowercase is invalid

    def test_decode_invalid_length_short(self):
        with self.assertRaises(ValueError):
            decode_base4_direct("AGC")

    def test_decode_invalid_length_long(self):
        with self.assertRaises(ValueError):
            decode_base4_direct("AGCTA")

if __name__ == '__main__':
    unittest.main()
