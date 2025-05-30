from typing import Optional
from genecoder.encoders import encode_base4_direct, decode_base4_direct

def calculate_gc_content(dna_sequence: str) -> float:
    """Calculates the GC content of a DNA sequence.

    Args:
        dna_sequence: The DNA sequence string (e.g., "ATGC").

    Returns:
        The GC content as a float (e.g., 0.5 for 50%).
        Returns 0.0 for an empty sequence.
    """
    if not dna_sequence:
        return 0.0
    
    gc_count = dna_sequence.upper().count('G') + dna_sequence.upper().count('C')
    return gc_count / len(dna_sequence)

def check_homopolymer_length(dna_sequence: str, max_len: int) -> bool:
    """Checks if any homopolymer in the DNA sequence exceeds a maximum length.

    Args:
        dna_sequence: The DNA sequence string.
        max_len: The maximum allowed homopolymer length.

    Returns:
        True if any homopolymer is longer than max_len, otherwise False.
        Returns False for an empty sequence.
    """
    if not dna_sequence:
        return False

    current_char = ''
    current_len = 0
    for char in dna_sequence.upper():
        if char == current_char:
            current_len += 1
        else:
            current_char = char
            current_len = 1
        
        if current_len > max_len:
            return True
    return False

def encode_gc_balanced(data: bytes, target_gc_min: float, target_gc_max: float, max_homopolymer: int) -> str:
    """Encodes binary data into a DNA sequence with GC content and homopolymer constraints.

    Args:
        data: The binary data to encode.
        target_gc_min: The minimum target GC content (e.g., 0.4).
        target_gc_max: The maximum target GC content (e.g., 0.6).
        max_homopolymer: The maximum allowed homopolymer length.

    Returns:
        The encoded DNA sequence as a string. (Currently empty string)
    """
    """Encodes binary data into a DNA sequence with GC content and homopolymer constraints.

    Encoding Strategy:
    - Encodes data using `encode_base4_direct`.
    - If constraints (GC content, homopolymer length) are met, returns the sequence prefixed with "0".
    - If constraints are violated, inverts data bits, re-encodes, and returns prefixed with "1".
      (Assumes the alternative sequence is better without re-checking constraints).

    Args:
        data: The binary data to encode.
        target_gc_min: The minimum target GC content.
        target_gc_max: The maximum target GC content.
        max_homopolymer: The maximum allowed homopolymer length.

    Returns:
        The encoded DNA sequence as a string, prefixed with "0" or "1".
    """
    initial_sequence = encode_base4_direct(data, add_parity=False)

    gc_content_ok = target_gc_min <= calculate_gc_content(initial_sequence) <= target_gc_max
    homopolymer_ok = not check_homopolymer_length(initial_sequence, max_homopolymer)

    if gc_content_ok and homopolymer_ok:
        return "0" + initial_sequence
    else:
        # Invert data bits and re-encode
        modified_data = bytes(b ^ 0xFF for b in data) # XOR each byte with 0xFF to flip all bits
        alternative_sequence = encode_base4_direct(modified_data, add_parity=False)
        # Here, we assume the alternative sequence is better or acceptable.
        # A more sophisticated approach might re-check constraints for the alternative
        # or use a more complex encoding strategy if both fail.
        return "1" + alternative_sequence

def get_max_homopolymer_length(dna_sequence: str) -> int:
    """Calculates the length of the longest homopolymer in a DNA sequence.

    Args:
        dna_sequence: The DNA sequence string (e.g., "AAATTCGGGG").

    Returns:
        The length of the longest homopolymer. Returns 0 for an empty sequence.
    """
    if not dna_sequence:
        return 0

    max_len = 0
    current_len = 0
    if len(dna_sequence) > 0:
        current_char = dna_sequence[0]
        current_len = 1
        max_len = 1

    for i in range(1, len(dna_sequence)):
        if dna_sequence[i] == current_char:
            current_len += 1
        else:
            current_char = dna_sequence[i]
            current_len = 1
        
        if current_len > max_len:
            max_len = current_len
            
    return max_len if dna_sequence else 0


def decode_gc_balanced(
    dna_sequence: str,
    expected_gc_min: Optional[float] = None,
    expected_gc_max: Optional[float] = None,
    expected_max_homopolymer: Optional[int] = None
) -> bytes:
    """Decodes a DNA sequence (encoded by encode_gc_balanced) back into binary data.

    Optionally, expected constraints can be provided for future validation,
    though they are not used in the current decoding logic.

    Decoding Strategy:
    - Checks the first character (signal bit).
    - If "0", decodes the rest of the sequence directly.
    - If "1", decodes the rest, then inverts the bits of the result.

    Args:
        dna_sequence: The DNA sequence to decode.
        expected_gc_min: The expected minimum GC content (for future use).
        expected_gc_max: The expected maximum GC content (for future use).
        expected_max_homopolymer: The expected maximum homopolymer length (for future use).

    Returns:
        The decoded binary data.

    Raises:
        ValueError: If the sequence is too short or the signal bit is invalid.
    """
    # Current implementation does not use expected_gc_min, expected_gc_max, expected_max_homopolymer.
    # They are included for future extensibility, e.g., to verify if the decoded sequence
    # would have met these constraints if they were re-calculated on the payload.

    if not dna_sequence or len(dna_sequence) < 1: # Sequence must have at least signal bit
        raise ValueError("Input DNA sequence is too short to decode (missing signal bit).")

    signal_bit = dna_sequence[0]
    payload_dna_sequence = dna_sequence[1:]

    if not payload_dna_sequence: # Check if after removing signal bit, sequence is empty
        raise ValueError("Input DNA sequence is too short (only signal bit found, no payload).")

    if signal_bit == "0":
        decoded_data = decode_base4_direct(payload_dna_sequence, check_parity=False)
    elif signal_bit == "1":
        # Decode the payload first
        temp_decoded_data = decode_base4_direct(payload_dna_sequence, check_parity=False)
        # Then invert the bits of the decoded data
        decoded_data = bytes(b ^ 0xFF for b in temp_decoded_data)
    else:
        raise ValueError(f"Invalid signal bit: '{signal_bit}'. Expected '0' or '1'.")

    return decoded_data
