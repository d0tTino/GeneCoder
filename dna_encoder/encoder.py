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


import heapq
import collections

def encode_huffman4(data: bytes) -> tuple[str, dict[str, str]]:
    """
    Encodes a bytes object into a Huffman-coded string of bits,
    based on the frequencies of 2-bit chunks.

    The 4 symbols for Huffman coding are "00", "01", "10", "11".

    Args:
        data: The bytes object to encode.

    Returns:
        A tuple containing:
        - encoded_bits (str): A string of '0's and '1's representing
                              the Huffman encoded data.
        - huffman_codes (dict[str, str]): A dictionary mapping each 2-bit
                                         chunk (e.g., "00") to its
                                         Huffman code string (e.g., "01").
        Returns ("", {}) if the input data is empty.
    """
    if not data:
        return "", {}

    # 1. Convert Bytes to 2-bit Chunks
    two_bit_chunks = []
    for byte in data:
        binary_representation = format(byte, '08b')
        for i in range(0, 8, 2):
            two_bit_chunks.append(binary_representation[i:i+2])

    # 2. Calculate Frequencies
    frequencies = collections.Counter(two_bit_chunks)
    
    # Filter out chunks that are not present in the data
    # (though Counter will only have present ones anyway)
    # This ensures that only actual symbols from data are in the heap.
    present_symbols = {chunk: freq for chunk, freq in frequencies.items() if freq > 0}

    if not present_symbols: # Should not happen if data is not empty
        return "", {}

    # Handle single unique symbol case
    if len(present_symbols) == 1:
        symbol = list(present_symbols.keys())[0]
        huffman_codes = {symbol: "0"}
        encoded_bits = "0" * present_symbols[symbol]
        return encoded_bits, huffman_codes

    # 3. Build Huffman Tree using heapq
    priority_queue = [[weight, [symbol, ""]] for symbol, weight in present_symbols.items()]
    heapq.heapify(priority_queue)

    while len(priority_queue) > 1:
        lo = heapq.heappop(priority_queue)
        hi = heapq.heappop(priority_queue)
        for pair in lo[1:]: # Add '0' to codes for left branch
            pair[1] = '0' + pair[1]
        for pair in hi[1:]: # Add '1' to codes for right branch
            pair[1] = '1' + pair[1]
        # The structure of items in priority_queue for internal nodes is:
        # [frequency, [symbol1_info, code_path_for_symbol1], [symbol2_info, code_path_for_symbol2], ...]
        # When merging, we combine these lists.
        # The actual symbol is at pair[0], its developing code is pair[1]
        heapq.heappush(priority_queue, [lo[0] + hi[0]] + lo[1:] + hi[1:])

    # 4. Generate Huffman Codes from the tree structure
    # The priority_queue now contains a single item: the root of the tree.
    # The structure is [total_freq, [symbol1, code1], [symbol2, code2], ...]
    huffman_codes = {}
    if priority_queue: # Ensure queue is not empty
        root = priority_queue[0]
        for symbol_code_pair in root[1:]:
            symbol = symbol_code_pair[0]
            code = symbol_code_pair[1]
            huffman_codes[symbol] = code

    # 5. Encode Data
    encoded_bits_list = [huffman_codes[chunk] for chunk in two_bit_chunks]
    encoded_bits = "".join(encoded_bits_list)

    return encoded_bits, huffman_codes


def decode_huffman4(encoded_bits: str, huffman_codes: dict[str, str]) -> bytes:
    """
    Decodes a Huffman-encoded bit string back into bytes using a provided Huffman code map.

    Args:
        encoded_bits: A string of '0's and '1's representing the Huffman encoded data.
        huffman_codes: A dictionary mapping each 2-bit chunk (symbol) to its
                       Huffman code string. This is the map generated by encode_huffman4.

    Returns:
        The original decoded bytes object.

    Raises:
        ValueError: If encoded_bits is invalid (e.g., truncated, contains bits
                    that don't form a valid code) or if the resulting binary
                    string length is not a multiple of 8.
    """
    if not encoded_bits:
        # If huffman_codes is also empty (e.g. {} which came from encode_huffman4(b'')),
        # this is valid. If huffman_codes is not empty, it means we were given
        # an empty string to decode with a valid code table, which is also fine (empty result).
        return b""

    # Handle the case where huffman_codes might be empty but encoded_bits is not.
    # This would be an invalid state, but the loop logic below would raise ValueError.
    if not huffman_codes and encoded_bits: # Should ideally not happen with valid inputs
        raise ValueError("Encoded_bits is present, but huffman_codes map is empty.")

    # 1. Reverse Code Map for Efficient Lookup
    code_to_symbol_map = {code: symbol for symbol, code in huffman_codes.items()}

    # Handle single symbol encoding case where huffman_codes might be {"00": "0"}
    # and code_to_symbol_map is {"0": "00"}. If encoded_bits is "0000", this is valid.

    # 2. Decode Bit String
    decoded_two_bit_chunks = []
    current_code = ""
    for bit in encoded_bits:
        current_code += bit
        if current_code in code_to_symbol_map:
            decoded_two_bit_chunks.append(code_to_symbol_map[current_code])
            current_code = ""

    if current_code: # Check if any bits are remaining that didn't form a valid code
        raise ValueError("Invalid or truncated Huffman encoded sequence.")

    # 3. Convert 2-bit Chunks to Bytes
    if not decoded_two_bit_chunks: # e.g. if encoded_bits was "" and huffman_codes was valid but empty
        return b""

    full_binary_string = "".join(decoded_two_bit_chunks)

    if len(full_binary_string) % 8 != 0:
        raise ValueError("Decoded binary string length is not a multiple of 8.")

    if not full_binary_string: # Should be caught by previous decoded_two_bit_chunks check
        return b""

    byte_values = []
    for i in range(0, len(full_binary_string), 8):
        byte_chunk = full_binary_string[i:i+8]
        byte_values.append(int(byte_chunk, 2))

    return bytes(byte_values)
