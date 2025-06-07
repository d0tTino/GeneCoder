import unittest


from genecoder.encoders import encode_base4_direct, decode_base4_direct  # noqa: E402
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T  # noqa: E402

class TestBase4DirectMapping(unittest.TestCase):

    # Tests for encode_base4_direct
    def test_encode_empty(self):
        self.assertEqual(encode_base4_direct(b''), "")

    def test_encode_single_byte_zero(self):
        # 0b00000000 -> AAAA
        self.assertEqual(encode_base4_direct(b'\x00'), "AAAA")

    def test_encode_single_byte_max(self):
        # 0b11111111 -> TTTT
        self.assertEqual(encode_base4_direct(b'\xff'), "TTTT")

    def test_encode_ascii_char(self):
        # 'A' (ASCII 65) is 0b01000001
        # 01 -> C
        # 00 -> A
        # 00 -> A
        # 01 -> C
        # Expected: CAAC
        # The prompt example had 'A' (01000001) -> "ATAA". Let's check that.
        # 01 (C) 00 (A) 00 (A) 01 (C) -> "CAAC"
        # If "ATAA" is expected for 'A' (01000001):
        # A (00) T (01) A (00) A (00) -> 00010000. This is not 65.
        # The prompt description for encode_base4_direct states:
        # 1st pair: (byte >> 6) & 0b11
        # 2nd pair: (byte >> 4) & 0b11
        # 3rd pair: (byte >> 2) & 0b11
        # 4th pair: (byte >> 0) & 0b11
        # For byte 'A' = 0b01000001:
        # 1st pair: (01000001 >> 6) & 0b11 = 0b01 -> C
        # 2nd pair: (01000001 >> 4) & 0b11 = 0b0100 -> A
        # 3rd pair: (01000001 >> 2) & 0b11 = 0b010000 -> A
        # 4th pair: (01000001 >> 0) & 0b11 = 0b01000001 -> C
        # So, b'A' (01000001) should indeed be "CAAC".
        self.assertEqual(encode_base4_direct(b'A'), "CAAC")


    def test_encode_multiple_bytes(self):
        # 'H' (ASCII 72) is 0b01001000
        # 01 -> C
        # 00 -> A
        # 10 -> G
        # 00 -> A
        # Result: "CAGA"
        # 'i' (ASCII 105) is 0b01101001
        # 01 -> C
        # 10 -> G
        # 10 -> G
        # 01 -> C
        # Result: "CGGC"
        # Expected for "Hi": "CAGACGGC"
        # The prompt example is "ATCAATTG". Let's verify this.
        # 'H' = 01001000. If "ATCA":
        # A (00) T (01) C (10) A (00) -> 00011000 (Decimal 24). This is not 'H' (72).
        # Using the defined mapping:
        # H (01001000): 01(C) 00(A) 10(G) 00(A) -> "CAGA"
        # i (01101001): 01(C) 10(G) 10(G) 01(C) -> "CGGC"
        # So "Hi" -> "CAGACGGC".
        self.assertEqual(encode_base4_direct(b'Hi'), "CAGACGGC")

    def test_encode_byte_sequence(self):
        # \x12 -> 00010010 -> A(00)C(01)A(00)G(10) -> ACAG
        # \x34 -> 00110100 -> A(00)T(11)C(01)A(00) -> ATCA
        # \xAB -> 10101011 -> G(10)G(10)G(10)T(11) -> GGGT
        # \xCD -> 11001101 -> T(11)A(00)T(11)C(01) -> TATC
        # Expected: "ACAGATCAGGGTTATC"
        self.assertEqual(encode_base4_direct(b'\x12\x34\xAB\xCD'), "ACAGATCAGGGTTATC")

    # Tests for decode_base4_direct
    def test_decode_empty(self):
        decoded_data, errors = decode_base4_direct("")
        self.assertEqual(decoded_data, b'')
        self.assertEqual(errors, [])

    def test_decode_valid_sequence_aaaa(self):
        decoded_data, errors = decode_base4_direct("AAAA")
        self.assertEqual(decoded_data, b'\x00')
        self.assertEqual(errors, [])

    def test_decode_valid_sequence_gggg(self):
        decoded_data, errors = decode_base4_direct("TTTT")
        self.assertEqual(decoded_data, b'\xff')
        self.assertEqual(errors, [])

    def test_decode_ascii_char_reverse(self):
        # Corresponds to b'A' (01000001) which encodes to "CAAC"
        decoded_data, errors = decode_base4_direct("CAAC")
        self.assertEqual(decoded_data, b'A')
        self.assertEqual(errors, [])

    def test_decode_multiple_bytes_reverse(self):
        # Corresponds to b'Hi' which encodes to "CAGACGGC"
        decoded_data, errors = decode_base4_direct("CAGACGGC")
        self.assertEqual(decoded_data, b'Hi')
        self.assertEqual(errors, [])

    def test_decode_byte_sequence_reverse(self):
        # Corresponds to b'\x12\x34\xAB\xCD' which encodes to "ACAGATCAGGGTTATC"
        decoded_data, errors = decode_base4_direct("ACAGATCAGGGTTATC")
        self.assertEqual(decoded_data, b'\x12\x34\xAB\xCD')
        self.assertEqual(errors, [])

    # Test encode-decode consistency (round trip) - no parity
    def test_round_trip_empty_no_parity(self):
        data = b''
        encoded = encode_base4_direct(data)
        decoded, errors = decode_base4_direct(encoded)
        self.assertEqual(decoded, data)
        self.assertEqual(errors, [])

    def test_round_trip_simple_string_no_parity(self):
        data = b'Hello GeneCoder!'
        encoded = encode_base4_direct(data)
        decoded, errors = decode_base4_direct(encoded)
        self.assertEqual(decoded, data)
        self.assertEqual(errors, [])

    def test_round_trip_various_bytes_no_parity(self):
        data = b'\x00\x01\xFA\x80\x7F\xff'
        encoded = encode_base4_direct(data)
        decoded, errors = decode_base4_direct(encoded)
        self.assertEqual(decoded, data)
        self.assertEqual(errors, [])

    # Test decode_base4_direct error handling (no parity check)
    def test_decode_invalid_character(self):
        with self.assertRaises(ValueError):
            decode_base4_direct("AGCX") 

    def test_decode_invalid_character_lowercase(self):
        with self.assertRaises(ValueError):
            decode_base4_direct("agct")

    def test_decode_invalid_length_short(self):
        with self.assertRaises(ValueError):
            decode_base4_direct("AGC")

    def test_decode_invalid_length_long(self):
        with self.assertRaises(ValueError):
            decode_base4_direct("AGCTA")

    # --- Tests for Parity Integration ---
    def test_encode_base4_with_parity(self):
        # b'\x12\x34' -> "ACAGATCA" with the current mapping
        # Parity for "ACA" (1 GC) -> T.
        # Parity for "GAT" (1 GC) -> T.
        # Parity for "CA" (1 GC) -> T.
        # Expected: blocks "ACAT", "GATT", "CAT"
        # Let's re-verify \x12\x34 with my encoder:
        # \x12 (00010010): 00(A) 01(C) 00(A) 10(G) -> "ACAG"
        # \x34 (00110100): 00(A) 11(T) 01(C) 00(A) -> "ATCA"
        # Raw DNA: "ACAGATCA"
        # k_value=3
        # Block 1: "ACA" (GC=1, odd) -> Parity 'T'. Output: "ACAT"
        # Block 2: "GAT" (GC=1, odd) -> Parity 'T'. Output: "GATT"
        # Block 3: "CA"  (GC=1, odd) -> Parity 'T'. Output: "CAT"
        # Expected DNA with parity: "ACATGATTCAT"
        expected_dna_with_parity = "ACATGATTCAT"
        actual_dna_with_parity = encode_base4_direct(
            b'\x12\x34', add_parity=True, k_value=3, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
        )
        self.assertEqual(actual_dna_with_parity, expected_dna_with_parity)

    def test_decode_base4_with_parity_no_errors(self):
        # Using the corrected expected_dna_with_parity from above
        dna_with_parity = "ACATGATTCAT"  # Corresponds to b'\x12\x34' with k=3 parity
        original_data = b'\x12\x34'
        
        decoded_data, errors = decode_base4_direct(
            dna_with_parity, check_parity=True, k_value=3, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
        )
        self.assertEqual(decoded_data, original_data)
        self.assertEqual(errors, [])

    def test_decode_base4_with_parity_with_errors(self):
        # dna_with_parity = "ACATGATTCAT" (correct)
        # Corrupt first parity bit: "ACAAGATTCAT" (T -> A)
        # Block 1: "ACA", Parity "A". Expected for "ACA" (GC=1, odd) is "T". Error.
        corrupted_dna = "ACAAGATTCAT"
        original_data_stripped = b'\x12\x34' # This should still be decodable
        
        decoded_data, errors = decode_base4_direct(
            corrupted_dna, check_parity=True, k_value=3, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
        )
        self.assertEqual(decoded_data, original_data_stripped)
        self.assertEqual(errors, [0]) # Error expected in the first block (index 0)

    def test_round_trip_base4_with_parity(self):
        data = b"TestParity!"
        k_val = 5
        
        encoded_dna = encode_base4_direct(
            data, add_parity=True, k_value=k_val, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
        )
        decoded_data, errors = decode_base4_direct(
            encoded_dna, check_parity=True, k_value=k_val, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
        )
        
        self.assertEqual(decoded_data, data)
        self.assertEqual(errors, [], "No parity errors should be detected on a clean round trip.")

if __name__ == '__main__':
    unittest.main()
