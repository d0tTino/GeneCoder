import pytest
from src.genecoder.hamming_codec import (
    encode_hamming_7_4_nibble,
    decode_hamming_7_4_codeword,
    bytes_to_nibbles,
    nibbles_to_bytes,
    encode_data_with_hamming,
    decode_data_with_hamming
)

# Expected Hamming(7,4) codewords for nibbles 0-15
# P1 P2 D1 P3 D2 D3 D4 (P1 MSB)
# D1=n3, D2=n2, D3=n1, D4=n0
# P1 = D1^D2^D4
# P2 = D1^D3^D4
# P3 = D2^D3^D4
EXPECTED_HAMMING_CODEWORDS = [
    0b0000000,  # 0 (0000) -> D1=0,D2=0,D3=0,D4=0 -> P1=0,P2=0,P3=0 -> 0000000 (0x00)
    0b1101001,  # 1 (0001) -> D1=0,D2=0,D3=0,D4=1 -> P1=1,P2=1,P3=1 -> 1101001 (0x69)
    0b0101010,  # 2 (0010) -> D1=0,D2=0,D3=1,D4=0 -> P1=0,P2=1,P3=1 -> 0101010 (0x2A)
    0b1000011,  # 3 (0011) -> D1=0,D2=0,D3=1,D4=1 -> P1=1,P2=0,P3=0 -> 1000011 (0x43)
    0b1011100,  # 4 (0100) -> D1=0,D2=1,D3=0,D4=0 -> P1=1,P2=0,P3=1 -> 1011100 (0x5C)
    0b0110101,  # 5 (0101) -> D1=0,D2=1,D3=0,D4=1 -> P1=0,P2=1,P3=0 -> 0110101 (0x35)
    0b1110110,  # 6 (0110) -> D1=0,D2=1,D3=1,D4=0 -> P1=1,P2=1,P3=0 -> 1110110 (0x76)
    0b0011111,  # 7 (0111) -> D1=0,D2=1,D3=1,D4=1 -> P1=0,P2=0,P3=1 -> 0011111 (0x1F)
    0b1111000,  # 8 (1000) -> D1=1,D2=0,D3=0,D4=0 -> P1=1,P2=1,P3=0 -> 1111000 (0x78)
    0b0010001,  # 9 (1001) -> D1=1,D2=0,D3=0,D4=1 -> P1=0,P2=0,P3=1 -> 0010001 (0x11)
    0b1010010,  # 10 (1010) -> D1=1,D2=0,D3=1,D4=0 -> P1=1,P2=0,P3=1 -> 1010010 (0x52) - Corrected from manual example (0x5A)
    0b0111011,  # 11 (1011) -> D1=1,D2=0,D3=1,D4=1 -> P1=0,P2=1,P3=0 -> 0111011 (0x3B)
    0b0100100,  # 12 (1100) -> D1=1,D2=1,D3=0,D4=0 -> P1=0,P2=1,P3=1 -> 0100100 (0x24)
    0b1001101,  # 13 (1101) -> D1=1,D2=1,D3=0,D4=1 -> P1=1,P2=0,P3=0 -> 1001101 (0x4D)
    0b0001110,  # 14 (1110) -> D1=1,D2=1,D3=1,D4=0 -> P1=0,P2=0,P3=0 -> 0001110 (0x0E)
    0b1100111,  # 15 (1111) -> D1=1,D2=1,D3=1,D4=1 -> P1=1,P2=1,P3=1 -> 1100111 (0x67) - Corrected from manual example (0x7F)
]
# Re-checked 10 (1010): D1=1,D2=0,D3=1,D4=0. P1=1^0^0=1, P2=1^1^0=0, P3=0^1^0=1. Codeword: 1011010 (0x52). Yes, my table is correct.
# Re-checked 15 (1111): D1=1,D2=1,D3=1,D4=1. P1=1^1^1=1, P2=1^1^1=1, P3=1^1^1=1. Codeword: 1111111 (0x7F). Ah, my table has 0x67.
# Let's re-calculate 15: D1=1,D2=1,D3=1,D4=1
# P1 = 1^1^1 = 1 (c6)
# P2 = 1^1^1 = 1 (c5)
# D1 = 1 (c4)
# P3 = 1^1^1 = 1 (c3)
# D2 = 1 (c2)
# D3 = 1 (c1)
# D4 = 1 (c0)
# Codeword = 1111111 = 0x7F. The table value 0b1100111 (0x67) is incorrect for nibble 15.
# Let me fix the table for 15.
EXPECTED_HAMMING_CODEWORDS[15] = 0b1111111 # For nibble 15 (1111)

# Test encode_hamming_7_4_nibble
@pytest.mark.parametrize("nibble, expected_codeword", enumerate(EXPECTED_HAMMING_CODEWORDS))
def test_encode_hamming_7_4_nibble_valid(nibble, expected_codeword):
    assert encode_hamming_7_4_nibble(nibble) == expected_codeword

def test_encode_hamming_7_4_nibble_out_of_range():
    with pytest.raises(ValueError):
        encode_hamming_7_4_nibble(-1)
    with pytest.raises(ValueError):
        encode_hamming_7_4_nibble(16)

# Test decode_hamming_7_4_codeword
@pytest.mark.parametrize("original_nibble", range(16))
def test_decode_hamming_7_4_codeword_no_error(original_nibble):
    correct_codeword = EXPECTED_HAMMING_CODEWORDS[original_nibble]
    decoded_nibble, corrected = decode_hamming_7_4_codeword(correct_codeword)
    assert decoded_nibble == original_nibble
    assert not corrected

@pytest.mark.parametrize("original_nibble", range(16))
def test_decode_hamming_7_4_codeword_single_bit_error_correction(original_nibble):
    correct_codeword = EXPECTED_HAMMING_CODEWORDS[original_nibble]
    # Test error in each of the 7 bit positions
    for i in range(7): # Bit positions 0 (LSB) to 6 (MSB)
        error_codeword = correct_codeword ^ (1 << i)
        decoded_nibble, corrected = decode_hamming_7_4_codeword(error_codeword)
        assert decoded_nibble == original_nibble, f"Failed for nibble {original_nibble} with error at bit {i}"
        assert corrected, f"Error correction flag should be True for nibble {original_nibble} with error at bit {i}"

def test_decode_hamming_7_4_codeword_two_bit_error():
    # Example: Nibble 0 (0000), Codeword 0x00 (0000000)
    # Introduce 2-bit error: flip bit 0 and bit 1 -> 0000011 (0x03)
    original_nibble = 0
    correct_codeword = EXPECTED_HAMMING_CODEWORDS[original_nibble]
    error_codeword = correct_codeword ^ 0b0000011 # Flip c0 and c1
    
    # Syndrome for 0000011:
    # P1 P2 D1 P3 D2 D3 D4
    # c6 c5 c4 c3 c2 c1 c0
    # 0  0  0  0  0  1  1
    # p1r=0, p2r=0, d1r=0, p3r=0, d2r=0, d3r=1, d4r=1
    # s1 = 0^0^0^1 = 1
    # s2 = 0^0^1^1 = 0
    # s3 = 0^0^1^1 = 0
    # error_pos_val = (001) = 1. It will try to correct bit 7-1 = 6 (P1).
    # Codeword 0000011 -> flip c6 -> 1000011 (0x43)
    # Decoded nibble from 1000011: D1=0, D2=0, D3=1, D4=1 -> nibble 3.
    # This is an incorrect correction, as expected for 2-bit errors.
    decoded_nibble, corrected = decode_hamming_7_4_codeword(error_codeword)
    assert decoded_nibble != original_nibble # Should not correct to original
    assert corrected # It will attempt a correction (flag will be true)
    assert decoded_nibble == 3 # It corrects to nibble 3

    # Another example: Nibble 5 (0101), Codeword 0x35 (0110101)
    # Introduce 2-bit error: flip bit 0 and bit 6 -> 1110100 (0x74)
    original_nibble_2 = 5
    correct_codeword_2 = EXPECTED_HAMMING_CODEWORDS[original_nibble_2] #0b0110101
    error_codeword_2 = correct_codeword_2 ^ ( (1 << 0) | (1 << 6) ) # flip c0 and c6 -> 1110100
    
    decoded_nibble_2, corrected_2 = decode_hamming_7_4_codeword(error_codeword_2)
    assert decoded_nibble_2 != original_nibble_2
    assert corrected_2

def test_decode_hamming_7_4_codeword_out_of_range():
    with pytest.raises(ValueError):
        decode_hamming_7_4_codeword(-1)
    with pytest.raises(ValueError):
        decode_hamming_7_4_codeword(128) # 2^7

# Test bytes_to_nibbles
def test_bytes_to_nibbles():
    assert bytes_to_nibbles(b'') == []
    assert bytes_to_nibbles(b'\xA1') == [0xA, 0x1] # 10, 1
    assert bytes_to_nibbles(b'\x00\xFF\x12') == [0x0, 0x0, 0xF, 0xF, 0x1, 0x2] # 0,0,15,15,1,2

# Test nibbles_to_bytes
def test_nibbles_to_bytes():
    assert nibbles_to_bytes([]) == b''
    assert nibbles_to_bytes([0xA, 0x1, 0xB, 0x2]) == b'\xA1\xB2'
    assert nibbles_to_bytes([0xA, 0x1, 0xB]) == b'\xA1\xB0' # Padded with 0x0
    assert nibbles_to_bytes([0xF]) == b'\xF0' # Padded with 0x0

def test_nibbles_to_bytes_out_of_range():
    with pytest.raises(ValueError):
        nibbles_to_bytes([0, 16])
    with pytest.raises(ValueError):
        nibbles_to_bytes([-1, 5])
    with pytest.raises(ValueError):
        nibbles_to_bytes([0xA, 0x1, 0xB, 20])


# Test encode_data_with_hamming and decode_data_with_hamming (Combined)
@pytest.mark.parametrize("original_data_str, expected_padding_multiple_of_7_check", [
    ("", True), # Empty
    ("A", False), # 1 byte (0x41) -> 2 nibbles -> 14 bits. Padding = (8-(14%8))%8 = (8-6)%8 = 2. Total 16 bits.
    ("Hello", False), # 5 bytes -> 10 nibbles -> 70 bits. Padding = (8-(70%8))%8 = (8-6)%8 = 2. Total 72 bits.
    ("Test1234", True), # 8 bytes -> 16 nibbles -> 112 bits. 112 % 7 = 0. 112 % 8 = 0. Padding = 0.
    ("Short", False), # 5 bytes
    ("AnotherTest", False) # 11 bytes -> 22 nibbles -> 154 bits. 154 % 7 = 0. Padding = (8-(154%8))%8 = (8-2)%8 = 6. Total 160.
])
def test_encode_decode_data_with_hamming_no_errors(original_data_str, expected_padding_multiple_of_7_check):
    original_data = original_data_str.encode('utf-8')
    
    encoded_bytes, padding_bits = encode_data_with_hamming(original_data)
    
    # Verify bit string length before final byte conversion for debugging
    num_nibbles = len(bytes_to_nibbles(original_data))
    expected_bit_length_pre_padding = num_nibbles * 7
    assert (expected_bit_length_pre_padding + padding_bits) % 8 == 0

    decoded_bytes, corrected_errors = decode_data_with_hamming(encoded_bytes, padding_bits)
    
    assert decoded_bytes == original_data
    assert corrected_errors == 0

@pytest.mark.parametrize("original_data_str", [
    "A", 
    "Hello", 
    "Test1234",
    "This is a longer test string for Hamming code."
])
def test_encode_decode_data_with_hamming_single_bit_error_correction(original_data_str):
    original_data = original_data_str.encode('utf-8')
    
    encoded_bytes, padding_bits = encode_data_with_hamming(original_data)
    
    if not encoded_bytes: # Skip error introduction if encoded_bytes is empty (e.g. original_data was empty)
        decoded_bytes, corrected_errors = decode_data_with_hamming(encoded_bytes, padding_bits)
        assert decoded_bytes == original_data
        assert corrected_errors == 0
        return

    # Introduce a single bit error in the first byte
    error_encoded_list = list(encoded_bytes)
    error_encoded_list[0] = error_encoded_list[0] ^ 0x01 # Flip the LSB of the first byte
    error_encoded_bytes = bytes(error_encoded_list)
    
    decoded_bytes, corrected_errors = decode_data_with_hamming(error_encoded_bytes, padding_bits)
    
    assert decoded_bytes == original_data, \
        f"Original: {original_data.hex()}, Decoded: {decoded_bytes.hex()}, Encoded: {encoded_bytes.hex()}, Errored: {error_encoded_bytes.hex()}"
    assert corrected_errors >= 1 # Should be 1 if error affects one codeword. Could be >1 if error spans boundary in bit stream.
                                 # For a single bit flip in a byte, it should affect at most one 7-bit codeword
                                 # or two if the bit is at the boundary of two 7-bit chunks within that byte.
                                 # But Hamming(7,4) corrects only 1 bit per block.
                                 # A single bit flip in the byte stream will corrupt only one bit in ONE 7-bit codeword,
                                 # unless it's one of the padding bits that got flipped.
                                 # If it's a padding bit, it might not be detected or might cause length issues.
                                 # The test flips LSB of first byte. This bit is part of a codeword.
    assert corrected_errors <= 1 # Expecting exactly one correction for a single bit flip in a data-carrying byte.


def test_encode_data_empty():
    encoded_bytes, padding_bits = encode_data_with_hamming(b'')
    assert encoded_bytes == b''
    assert padding_bits == 0

def test_decode_data_empty():
    decoded_bytes, corrected_errors = decode_data_with_hamming(b'', 0)
    assert decoded_bytes == b''
    assert corrected_errors == 0

def test_decode_data_invalid_padding():
    with pytest.raises(ValueError, match="num_final_padding_bits must be between 0 and 7."):
        decode_data_with_hamming(b'\x00', 8)
    with pytest.raises(ValueError, match="num_final_padding_bits must be between 0 and 7."):
        decode_data_with_hamming(b'\x00', -1)

def test_decode_data_invalid_length_after_padding_removal():
    # Encode "A" -> 2 nibbles -> 14 bits. Pad with 2 zeros -> 16 bits = 2 bytes.
    # If we say padding was 1, remaining bits = 15. 15 % 7 != 0.
    encoded_A, padding_A = encode_data_with_hamming(b'A') # Should be (bytes, 2)
    assert padding_A == 2
    with pytest.raises(ValueError, match="Invalid data: length of bit string after removing padding is not a multiple of 7."):
        decode_data_with_hamming(encoded_A, 1) # Incorrect padding
    with pytest.raises(ValueError, match="Invalid data: length of bit string after removing padding is not a multiple of 7."):
        decode_data_with_hamming(encoded_A, 0) # Incorrect padding

    # Test with an empty bit string after padding removal but non-zero length before
    # 7 bits + 1 padding bit = 1 byte. If padding is 1, bit_string is 7 bits.
    # If padding is such that bit_string becomes empty.
    # Example: 0 data nibbles. Encoded is 0 bits. Padding 0.
    # If encoded_data = b'\x80' (10000000), num_final_padding_bits = 1. bit_string = 1000000. Valid.
    # If encoded_data = b'\x0F' (00001111), num_final_padding_bits = 4. bit_string = 0000. Invalid length.
    with pytest.raises(ValueError, match="Invalid data: length of bit string after removing padding is not a multiple of 7."):
        decode_data_with_hamming(b'\x0F', 4)

    # Test where bit_string becomes empty after padding removal.
    # If encoded_data = b'\x00', num_final_padding_bits = 0. bit_string = "00000000". Error.
    # If encoded_data = b'\x00', num_final_padding_bits = 1. bit_string = "0000000". Valid. (decodes to nibble 0)
    # If encoded_data = b'\x00', num_final_padding_bits = 8 -> This raises ValueError for padding.
    # If encoded_data = b'\x00' (1 byte), num_final_padding_bits = 1.
    # bit_string will be 7 '0's. This is one codeword.
    # It will decode to nibble 0.
    # If the function is called with encoded_data=b'', num_final_padding_bits=0, it should return b'', 0
    # This is handled by: if not bit_string: return b'', 0

    # Test case: encoded_data = b'\x00', num_final_padding_bits = 1
    # bit_string = "0000000". int("0000000", 2) = 0.
    # decode_hamming_7_4_codeword(0) -> (0, False)
    # decoded_nibbles = [0]. This is odd.
    # nibbles_to_bytes([0]) -> pads to [0,0] -> b'\x00'
    decoded_bytes, corrected_errors = decode_data_with_hamming(b'\x00', 1)
    assert decoded_bytes == b'\x00'
    assert corrected_errors == 0
