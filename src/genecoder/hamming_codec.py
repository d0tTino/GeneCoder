def encode_hamming_7_4_nibble(nibble: int) -> int:
    """Encodes a 4-bit nibble into a 7-bit Hamming(7,4) codeword."""
    if not (0 <= nibble <= 15):
        raise ValueError("Input nibble must be between 0 and 15.")

    # Break the nibble into individual data bits (d1..d4). ``d1`` is the most
    # significant bit.  Shifts and masks are used to isolate each bit.
    d1 = (nibble >> 3) & 1
    d2 = (nibble >> 2) & 1
    d3 = (nibble >> 1) & 1
    d4 = nibble & 1

    # Compute the parity bits placed at positions 1, 2 and 4 of the final
    # codeword.  Each parity is the XOR of a subset of the data bits according
    # to the Hamming(7,4) specification.
    p1 = d1 ^ d2 ^ d4
    p2 = d1 ^ d3 ^ d4
    p3 = d2 ^ d3 ^ d4

    # Assemble the codeword. The bit layout from MSB to LSB is:
    # p1 p2 d1 p3 d2 d3 d4
    #      6  5  4  3  2  1  0 (bit positions)
    return (
        (p1 << 6)
        | (p2 << 5)
        | (d1 << 4)
        | (p3 << 3)
        | (d2 << 2)
        | (d3 << 1)
        | d4
    )


# Precompute the 16 valid Hamming codewords and an error lookup table
_HAMMING_CODEWORDS: list[int] = [encode_hamming_7_4_nibble(n) for n in range(16)]
_ERROR_LOOKUP: dict[int, tuple[int, bool]] = {}


def _build_lookup() -> None:
    """Builds the lookup table for decoding, including single-bit errors."""
    global _ERROR_LOOKUP
    _ERROR_LOOKUP = {}
    for nib, valid in enumerate(_HAMMING_CODEWORDS):
        # Map the valid codeword back to its nibble with the ``corrected`` flag
        # set to False.
        _ERROR_LOOKUP[valid] = (nib, False)
        # Pre-compute all single-bit error variants of this codeword.  Each is
        # associated with the original nibble and ``True`` to indicate a
        # correction would be necessary.
        for i in range(7):
            erroneous = valid ^ (1 << i)
            if erroneous not in _ERROR_LOOKUP:
                _ERROR_LOOKUP[erroneous] = (nib, True)

def decode_hamming_7_4_codeword(codeword: int) -> tuple[int, bool]:
    """Decodes a 7-bit Hamming(7,4) codeword with single-bit error correction."""
    if not (0 <= codeword <= 127):
        raise ValueError("Input codeword must be between 0 and 127.")

    # Lazily build the lookup table on first use
    if "_ERROR_LOOKUP" not in globals():
        _build_lookup()

    if codeword in _ERROR_LOOKUP:
        return _ERROR_LOOKUP[codeword]

    # Fallback to minimal-distance search (handles unexpected patterns)
    best_nibble = 0
    best_distance = 8
    for nibble, valid in enumerate(_HAMMING_CODEWORDS):
        distance = bin(codeword ^ valid).count("1")
        if distance < best_distance:
            best_distance = distance
            best_nibble = nibble
    return best_nibble, best_distance > 0


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
        # Split each byte into its high and low 4-bit halves.
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
    processed_nibbles = list(nibbles)  # Work on a copy so the input is unchanged
    if len(processed_nibbles) % 2 != 0:
        # If the number of nibbles is odd, append a zero to form a final byte.
        processed_nibbles.append(0x0)

    byte_list: list[int] = []
    for i in range(0, len(processed_nibbles), 2):
        msb_nibble = processed_nibbles[i]
        lsb_nibble = processed_nibbles[i+1]
        if not (0 <= msb_nibble <= 15 and 0 <= lsb_nibble <= 15):
            raise ValueError("All nibbles must be between 0 and 15.")
        # Recombine the two nibbles into a single byte.
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

    # Bit Packing. Each 7-bit codeword is concatenated into a single bit string
    # before being split into bytes.
    bit_string = ""
    for codeword in codewords_7bit:
        bit_string += format(codeword, "07b")  # Convert codeword to a 7-char string

    num_total_bits = len(bit_string)
    # Calculate how many zero bits are required to align the bit stream to a
    # whole byte.  ``num_padding_bits_at_end`` is in the range 0-7.
    num_padding_bits_at_end = (8 - (num_total_bits % 8)) % 8

    # Append padding zeros so the string length becomes a multiple of eight.
    bit_string += "0" * num_padding_bits_at_end
    
    encoded_bytes_list: list[int] = []
    for i in range(0, len(bit_string), 8):
        byte_str = bit_string[i:i+8]
        # Convert each 8-bit chunk into an integer byte.
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
    # Recreate the full bit stream from the encoded bytes.  Each byte is
    # represented by eight binary characters.
    for byte_val in encoded_data:
        bit_string += format(byte_val, "08b")

    if num_final_padding_bits > 0:
        # Strip the padding bits that were added during encoding.
        bit_string = bit_string[:-num_final_padding_bits]

    # After removing padding the bit stream must be divisible into 7-bit
    # codewords. Any remainder indicates corrupted or incorrectly padded data.
    if len(bit_string) % 7 != 0:
        raise ValueError(
            "Invalid data: length of bit string after removing padding "
            "is not a multiple of 7."
        )

    if not bit_string: # Handle case where bit_string becomes empty after padding removal
        return b'', 0

    codewords_7bit_str: list[str] = []
    for i in range(0, len(bit_string), 7):
        # Slice the stream into 7-bit segments representing individual codewords.
        codewords_7bit_str.append(bit_string[i:i+7])

    decoded_nibbles: list[int] = []
    corrected_errors_count = 0
    
    for codeword_str in codewords_7bit_str:
        codeword_int = int(codeword_str, 2)
        nibble, corrected = decode_hamming_7_4_codeword(codeword_int)
        decoded_nibbles.append(nibble)
        if corrected:
            # ``corrected`` is True when the lookup determined a single-bit
            # error and returned the corrected nibble.
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
