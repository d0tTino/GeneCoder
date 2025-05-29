def encode_base4(data: bytes) -> str:
    """
    Encodes a bytes object into a DNA sequence string using a base-4 representation.

    Args:
        data: The bytes object to encode.

    Returns:
        A string representing the DNA sequence.
        Returns an empty string if the input data is empty.
    """
    if not data:
        return ""

    binary_string = ""
    for byte in data:
        # Convert byte to its 8-bit binary representation, padding with leading zeros
        binary_string += format(byte, '08b')

    dna_sequence = ""
    for i in range(0, len(binary_string), 2):
        chunk = binary_string[i:i+2]
        if chunk == "00":
            dna_sequence += "A"
        elif chunk == "01":
            dna_sequence += "C"
        elif chunk == "10":
            dna_sequence += "G"
        elif chunk == "11":
            dna_sequence += "T"
        # It's guaranteed that chunks will be one of these, so no else is needed.
        # However, if the binary_string length is odd, the last chunk will be a single bit.
        # The problem description implies that the concatenated 8-bit strings will always
        # result in an even length string, so each chunk will be 2 bits.
        # For example, b'H' (01001000) -> 01,00,10,00 -> C,A,G,A

    return dna_sequence


def decode_base4(dna_sequence: str) -> bytes:
    """
    Decodes a DNA sequence string (base-4 representation) into a bytes object.

    Args:
        dna_sequence: The DNA sequence string to decode, composed of 'A', 'C', 'G', 'T'.

    Returns:
        A bytes object representing the original data.
        Returns an empty bytes object (b'') if the input dna_sequence is empty.

    Raises:
        ValueError: If the input sequence contains invalid characters or
                    if its length is not valid for byte conversion.
    """
    if not dna_sequence:
        return b""

    binary_string = ""
    dna_to_binary_map = {
        'A': "00",
        'C': "01",
        'G': "10",
        'T': "11"
    }

    for char in dna_sequence:
        binary_chunk = dna_to_binary_map.get(char)
        if binary_chunk is None:
            raise ValueError(f"Invalid character in DNA sequence: {char}")
        binary_string += binary_chunk

    if len(binary_string) % 8 != 0:
        raise ValueError("Invalid DNA sequence length for byte conversion.")

    byte_values = []
    for i in range(0, len(binary_string), 8):
        byte_chunk = binary_string[i:i+8]
        byte_values.append(int(byte_chunk, 2))

    return bytes(byte_values)
