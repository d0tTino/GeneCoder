def encode_hamming_7_4_nibble(nibble: int) -> int:
    """Encodes a 4-bit nibble into a 7-bit Hamming(7,4) codeword.

    The input nibble (0-15) is treated as D1 D2 D3 D4, where D1 is the MSB.
    Example: nibble = 10 (binary 1010) -> D1=1, D2=0, D3=1, D4=0.

    The 7-bit codeword is structured as P1 P2 D1 P3 D2 D3 D4, where P1 is the MSB.
    Bit positions (0-indexed from LSB, 6-indexed from MSB):
    c6 c5 c4 c3 c2 c1 c0
    P1 P2 D1 P3 D2 D3 D4

    Parity bits are calculated for even parity:
    P1 (c6) covers D1(c4), D2(c2), D4(c0)  => P1 = D1^D2^D4
    P2 (c5) covers D1(c4), D3(c1), D4(c0)  => P2 = D1^D3^D4
    P3 (c3) covers D2(c2), D3(c1), D4(c0)  => P3 = D2^D3^D4

    Args:
        nibble: An integer representing the 4-bit data (0-15).

    Returns:
        An integer representing the 7-bit Hamming codeword.

    Raises:
        ValueError: If the input nibble is outside the 0-15 range.
    """
    if not (0 <= nibble <= 15):
        raise ValueError("Input nibble must be between 0 and 15.")

    # Extract data bits from the nibble: D1 D2 D3 D4 (D1 is MSB of data)
    # Nibble: n3 n2 n1 n0
    # D1 (c4) = n3 (nibble's MSB)
    # D2 (c2) = n2
    # D3 (c1) = n1
    # D4 (c0) = n0 (nibble's LSB)

    d1 = (nibble >> 3) & 1  # MSB of nibble
    d2 = (nibble >> 2) & 1
    d3 = (nibble >> 1) & 1
    d4 = (nibble >> 0) & 1  # LSB of nibble

    # Calculate parity bits (even parity)
    p1 = d1 ^ d2 ^ d4
    p2 = d1 ^ d3 ^ d4
    p3 = d2 ^ d3 ^ d4

    # Construct the 7-bit codeword: P1 P2 D1 P3 D2 D3 D4
    # c6=P1, c5=P2, c4=D1, c3=P3, c2=D2, c1=D3, c0=D4
    codeword = (
        (p1 << 6) | (p2 << 5) | (d1 << 4) | (p3 << 3) |
        (d2 << 2) | (d3 << 1) | (d4 << 0)
    )

    return codeword

def decode_hamming_7_4_codeword(codeword: int) -> tuple[int, bool]:
    """Decodes a 7-bit Hamming(7,4) codeword, correcting a single-bit error if present.

    The 7-bit codeword is assumed to be P1 P2 D1 P3 D2 D3 D4 (P1 is MSB).
    Bit positions (0-indexed from LSB, 6-indexed from MSB):
    c6 c5 c4 c3 c2 c1 c0
    P1 P2 D1 P3 D2 D3 D4

    Syndrome bits (s1, s2, s3) are calculated for even parity checks:
    s1 = P1^D1^D2^D4 (checks c6, c4, c2, c0)
    s2 = P2^D1^D3^D4 (checks c5, c4, c1, c0)
    s3 = P3^D2^D3^D4 (checks c3, c2, c1, c0)

    The error position is determined by (s3 s2 s1) as a binary number.
    If this value (err_pos_val, 1-7) is non-zero, the bit at that position
    in the codeword (1=P1 (MSB), ..., 7=D4 (LSB)) is flipped.

    Args:
        codeword: An integer representing the 7-bit codeword.

    Returns:
        A tuple (decoded_nibble, error_corrected_flag):
            - decoded_nibble: The 4-bit corrected data as an integer (0-15).
                              Data bits are D1 D2 D3 D4 (D1 is MSB).
            - error_corrected_flag: True if a single-bit error was detected and corrected,
                                    False otherwise.
    Raises:
        ValueError: If the input codeword is outside the 0-127 range.
    """
    if not (0 <= codeword <= 127):
        raise ValueError("Input codeword must be between 0 and 127.")

    # Extract received bits from the codeword
    # c6=P1, c5=P2, c4=D1, c3=P3, c2=D2, c1=D3, c0=D4
    p1_r = (codeword >> 6) & 1
    p2_r = (codeword >> 5) & 1
    d1_r = (codeword >> 4) & 1
    p3_r = (codeword >> 3) & 1
    d2_r = (codeword >> 2) & 1
    d3_r = (codeword >> 1) & 1
    d4_r = (codeword >> 0) & 1

    # Calculate syndrome bits
    s1 = p1_r ^ d1_r ^ d2_r ^ d4_r
    s2 = p2_r ^ d1_r ^ d3_r ^ d4_r
    s3 = p3_r ^ d2_r ^ d3_r ^ d4_r

    error_position_val = (s3 << 2) | (s2 << 1) | s1
    error_corrected_flag = False

    corrected_codeword = codeword

    if error_position_val != 0:
        error_corrected_flag = True
        # Flip the bit at the error position.
        # error_position_val is 1-7.
        # Position 1 is MSB (c6), Position 7 is LSB (c0).
        # The bit to flip is at index (7 - error_position_val) from MSB side (0-indexed c6..c0)
        # or (error_position_val - 1) from LSB side (0-indexed c0..c6)
        # Mask to flip is (1 << (7 - error_position_val))
        flip_mask = 1 << (7 - error_position_val)
        corrected_codeword = codeword ^ flip_mask

        # Re-extract bits if correction occurred
        d1_r = (corrected_codeword >> 4) & 1
        d2_r = (corrected_codeword >> 2) & 1
        d3_r = (corrected_codeword >> 1) & 1
        d4_r = (corrected_codeword >> 0) & 1
        # Parity bits are not re-extracted as they are not part of the decoded nibble

    # Reconstruct the 4-bit data nibble: D1 D2 D3 D4 (D1 is MSB)
    decoded_nibble = (d1_r << 3) | (d2_r << 2) | (d3_r << 1) | (d4_r << 0)

    return decoded_nibble, error_corrected_flag


# --- Byte-level and data-level Hamming coding functions ---

def bytes_to_nibbles(data: bytes) -> list[int]:
    """Converts a bytes object into a list of 4-bit integers (nibbles).

    Each byte is split into two nibbles: the most significant 4 bits first,
    followed by the least significant 4 bits.

    Args:
        data: A bytes object.

    Returns:
        A list of integers, where each integer represents a 4-bit nibble (0-15).
        Example: b'\\xA1' (10100001) -> [0xA, 0x1] ([10, 1]).
    """
    nibbles: list[int] = []
    for byte in data:
        msb_nibble = (byte >> 4) & 0x0F
        lsb_nibble = byte & 0x0F
        nibbles.append(msb_nibble)
        nibbles.append(lsb_nibble)
    return nibbles

def nibbles_to_bytes(nibbles: list[int]) -> bytes:
    """Converts a list of 4-bit integers (nibbles) back into a bytes object.

    If the list has an odd number of nibbles, it's padded with a final 0x0
    nibble to make its length even before conversion. Each pair of nibbles
    forms a byte, with the first nibble in the pair being the most significant.

    Args:
        nibbles: A list of integers, each representing a 4-bit nibble (0-15).

    Returns:
        A bytes object reconstructed from the nibbles.
        Example: [0xA, 0x1, 0xB, 0x2] -> b'\\xA1\\xB2'.
                 [0xA, 0x1, 0xB] -> (padded to [0xA, 0x1, 0xB, 0x0]) -> b'\\xA1\\xB0'.

    Raises:
        ValueError: If any nibble is outside the 0-15 range.
    """
    processed_nibbles = list(nibbles) # Create a copy to potentially modify
    if len(processed_nibbles) % 2 != 0:
        processed_nibbles.append(0x0) # Pad with a zero nibble if odd length

    byte_list: list[int] = []
    for i in range(0, len(processed_nibbles), 2):
        msb_nibble = processed_nibbles[i]
        lsb_nibble = processed_nibbles[i+1]
        if not (0 <= msb_nibble <= 15 and 0 <= lsb_nibble <= 15):
            raise ValueError("All nibbles must be between 0 and 15.")
        byte_val = (msb_nibble << 4) | lsb_nibble
        byte_list.append(byte_val)
    return bytes(byte_list)

def encode_data_with_hamming(data: bytes) -> tuple[bytes, int]:
    """Encodes byte data using Hamming(7,4) for each nibble and packs into bytes.

    1. Converts input bytes to a list of 4-bit nibbles.
    2. Encodes each nibble into a 7-bit Hamming codeword.
    3. Concatenates all 7-bit codewords into a single bit string.
    4. Pads this bit string with zero-bits at the end to make its total length
       a multiple of 8.
    5. Converts the padded bit string into bytes.

    Args:
        data: The input bytes to encode.

    Returns:
        A tuple (encoded_bytes, num_padding_bits_at_end):
            - encoded_bytes: The Hamming-encoded data, packed into bytes.
            - num_padding_bits_at_end: The number of zero-bits (0-7) added at the
                                       end of the bit string before byte conversion.
    """
    nibbles = bytes_to_nibbles(data)

    codewords_7bit: list[int] = []
    for nibble in nibbles:
        codewords_7bit.append(encode_hamming_7_4_nibble(nibble))

    if not codewords_7bit: # Handle empty input data
        return b'', 0

    # Bit Packing
    bit_string = ""
    for codeword in codewords_7bit:
        bit_string += format(codeword, '07b') # Convert 7-bit codeword to binary string

    num_total_bits = len(bit_string)
    num_padding_bits_at_end = (8 - (num_total_bits % 8)) % 8

    bit_string += '0' * num_padding_bits_at_end

    encoded_bytes_list: list[int] = []
    for i in range(0, len(bit_string), 8):
        byte_str = bit_string[i:i+8]
        encoded_bytes_list.append(int(byte_str, 2))

    return bytes(encoded_bytes_list), num_padding_bits_at_end

def decode_data_with_hamming(encoded_data: bytes, num_final_padding_bits: int) -> tuple[bytes, int]:
    """Decodes Hamming(7,4)-encoded byte data, correcting single-bit errors.

    1. Converts input bytes into a single bit string.
    2. Removes `num_final_padding_bits` from the end of this bit string.
    3. Validates if the remaining bit string length is a multiple of 7.
    4. Splits the bit string into 7-bit chunks (codewords).
    5. Decodes each 7-bit codeword using `decode_hamming_7_4_codeword`,
       counting corrected errors.
    6. Collects all decoded 4-bit nibbles.
    7. Converts the list of decoded nibbles back to bytes.
       (Note: `nibbles_to_bytes` handles potential padding if the original
       number of nibbles was odd, by adding a 0x0 nibble before its own conversion.
       This means the output here might have an extra null byte if the original
       data effectively had an odd number of nibbles and was thus padded by
       `bytes_to_nibbles` during encoding initially.)

    Args:
        encoded_data: The Hamming-encoded data bytes.
        num_final_padding_bits: The number of zero-bits that were added at the
                                end of the encoded bit string.

    Returns:
        A tuple (decoded_bytes, corrected_errors_count):
            - decoded_bytes: The original data, corrected for single-bit errors per codeword.
            - corrected_errors_count: The total number of corrected single-bit errors.

    Raises:
        ValueError: If `num_final_padding_bits` is invalid, or if the bit string
                    (after removing padding) is not a multiple of 7.
    """
    if not (0 <= num_final_padding_bits < 8):
        raise ValueError("num_final_padding_bits must be between 0 and 7.")

    bit_string = ""
    for byte_val in encoded_data:
        bit_string += format(byte_val, '08b')

    if num_final_padding_bits > 0:
        bit_string = bit_string[:-num_final_padding_bits]

    if len(bit_string) % 7 != 0:
        raise ValueError("Invalid data: length of bit string after removing padding "
                         "is not a multiple of 7.")

    if not bit_string: # Handle case where bit_string becomes empty after padding removal
        return b'', 0

    codewords_7bit_str: list[str] = []
    for i in range(0, len(bit_string), 7):
        codewords_7bit_str.append(bit_string[i:i+7])

    decoded_nibbles: list[int] = []
    corrected_errors_count = 0

    for codeword_str in codewords_7bit_str:
        codeword_int = int(codeword_str, 2)
        nibble, corrected = decode_hamming_7_4_codeword(codeword_int)
        decoded_nibbles.append(nibble)
        if corrected:
            corrected_errors_count += 1

    # The number of original data nibbles might have been odd.
    # `bytes_to_nibbles` always produces an even number of nibbles for encoding.
    # If the original data length implies an odd number of nibbles, `encode_data_with_hamming`
    # would have encoded an even number of nibbles.
    # `nibbles_to_bytes` will correctly form bytes, potentially adding a 0x0 if
    # the `decoded_nibbles` list has an odd length (which shouldn't happen if
    # `bytes_to_nibbles` always outputs even, and each nibble becomes a codeword).
    # The key is that `bytes_to_nibbles` ensures the list fed to Hamming encoding is even.
    # So, `decoded_nibbles` list should also be even.

    original_bytes = nibbles_to_bytes(decoded_nibbles)

    # Determine if the original data might have resulted in an odd number of nibbles.
    # This can be inferred if the number of encoded nibbles (len(decoded_nibbles))
    # was one greater than what an odd number of original bytes would produce.
    # However, the current design simplifies this: `bytes_to_nibbles` ensures an even
    # number of nibbles are encoded. `nibbles_to_bytes` handles padding if it receives
    # an odd list, but it shouldn't receive one from this flow.
    # The main concern is if the *original* data source had an odd number of nibbles.
    # If the original data had length N, it produced 2N nibbles.
    # The number of codewords is 2N. Total bits = 14N. Padding is (8 - (14N % 8)) % 8.
    # The number of decoded nibbles will be 2N.
    # `nibbles_to_bytes` will convert these 2N nibbles back into N bytes.
    # So, no special truncation logic is needed here based on `num_original_nibbles`
    # because `nibbles_to_bytes` handles its input based on its own padding rule if odd.
    # And `bytes_to_nibbles` ensures an even number of nibbles are always processed.

    return original_bytes, corrected_errors_count
