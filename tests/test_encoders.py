import unittest
from genecoder.encoders import encode_base4_direct, decode_base4_direct
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T

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
        decoded_data, errors = decode_base4_direct("")
        self.assertEqual(decoded_data, b'')
        self.assertEqual(errors, [])

    def test_decode_valid_sequence_aaaa(self):
        decoded_data, errors = decode_base4_direct("AAAA")
        self.assertEqual(decoded_data, b'\x00')
        self.assertEqual(errors, [])

    def test_decode_valid_sequence_gggg(self):
        decoded_data, errors = decode_base4_direct("GGGG")
        self.assertEqual(decoded_data, b'\xff')
        self.assertEqual(errors, [])

    def test_decode_ascii_char_reverse(self):
        # Corresponds to b'A' (01000001) which encodes to "TAAT"
        decoded_data, errors = decode_base4_direct("TAAT")
        self.assertEqual(decoded_data, b'A')
        self.assertEqual(errors, [])

    def test_decode_multiple_bytes_reverse(self):
        # Corresponds to b'Hi' which encodes to "TACATCCT"
        decoded_data, errors = decode_base4_direct("TACATCCT")
        self.assertEqual(decoded_data, b'Hi')
        self.assertEqual(errors, [])

    def test_decode_byte_sequence_reverse(self):
        # Corresponds to b'\x12\x34\xAB\xCD' which encodes to "ATACAGTACCCGGAGT"
        decoded_data, errors = decode_base4_direct("ATACAGTACCCGGAGT")
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
        # b'\x12\x34' -> "ATACAGTA" (corrected from "AATAACTA" in prompt based on current encoder)
        # Parity for "ATA" (0 GC) -> A.
        # Parity for "CAG" (1 GC) -> T.
        # Parity for "TA" (0 GC) -> A.
        # Expected: "ATAA CAGT TAA"
        # Let's re-verify \x12\x34 with my encoder:
        # \x12 (00010010): 00(A) 01(T) 00(A) 10(C) -> "ATAC"
        # \x34 (00110100): 00(A) 11(G) 01(T) 00(A) -> "AGTA"
        # Raw DNA: "ATACAGTA"
        # k_value=3
        # Block 1: "ATA" (GC=0, even) -> Parity 'A'. Output: "ATAA"
        # Block 2: "CAG" (GC=1, odd)  -> Parity 'T'. Output: "CAGT"
        # Block 3: "TA"  (GC=0, even) -> Parity 'A'. Output: "TAA"
        # Expected DNA with parity: "ATAACAGTTAA"
        expected_dna_with_parity = "ATAACAGTTAA"
        actual_dna_with_parity = encode_base4_direct(
            b'\x12\x34', add_parity=True, k_value=3, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
        )
        self.assertEqual(actual_dna_with_parity, expected_dna_with_parity)

    def test_decode_base4_with_parity_no_errors(self):
        # Using the corrected expected_dna_with_parity from above
        dna_with_parity = "ATAACAGTTAA" # Corresponds to b'\x12\x34' with k=3 parity
        original_data = b'\x12\x34'
        
        decoded_data, errors = decode_base4_direct(
            dna_with_parity, check_parity=True, k_value=3, parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T
        )
        self.assertEqual(decoded_data, original_data)
        self.assertEqual(errors, [])

    def test_decode_base4_with_parity_with_errors(self):
        # dna_with_parity = "ATAACAGTTAA" (correct)
        # Corrupt first parity bit: "ATATCAGTTAA" (A -> T)
        # Block 1: "ATA", Parity "T". Expected for "ATA" (0 GC, even) is "A". Error.
        # Block 2: "CAG", Parity "T". Expected for "CAG" (1 GC, odd) is "T". OK.
        # Block 3: "TA",  Parity "A". Expected for "TA"  (0 GC, even) is "A". OK.
        corrupted_dna = "ATATCAGTTAA" 
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
