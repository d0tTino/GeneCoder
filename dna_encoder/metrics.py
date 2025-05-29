def calculate_compression_ratio(original_size_bytes: int, 
                                encoded_payload_bits: int, 
                                huffman_table_bits: int = 0) -> float:
    """
    Calculates the compression ratio of an encoding scheme.

    The ratio is defined as (original size in bits) / (total encoded size in bits).
    - A ratio > 1.0 indicates compression (encoded size is smaller).
    - A ratio < 1.0 indicates expansion (encoded size is larger).
    - A ratio = 1.0 indicates no change in size.

    Args:
        original_size_bytes: The size of the original data in bytes.
        encoded_payload_bits: The size of the encoded data payload in bits
                              (e.g., length of the '0101...' string).
        huffman_table_bits: Optional. The size of the Huffman table or any other
                            metadata needed for decoding, in bits. Defaults to 0.

    Returns:
        The compression ratio as a float.

    Raises:
        TypeError: If any of the input arguments are not integers.
        ValueError: If any of the input arguments are negative.
    """
    if not all(isinstance(arg, int) for arg in [original_size_bytes, encoded_payload_bits, huffman_table_bits]):
        raise TypeError("All input arguments must be integers.")

    if original_size_bytes < 0 or encoded_payload_bits < 0 or huffman_table_bits < 0:
        raise ValueError("Input sizes/bits cannot be negative.")

    original_bits = original_size_bytes * 8
    total_encoded_bits = encoded_payload_bits + huffman_table_bits

    if total_encoded_bits == 0:
        if original_bits == 0: # original_size_bytes was 0
            return 1.0  # Empty input to empty output, ratio is 1.0
        else: # original_size_bytes > 0
            return float('inf') # Data loss or error, effectively infinite compression

    return original_bits / total_encoded_bits
