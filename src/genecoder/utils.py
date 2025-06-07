"""Utility helpers shared across modules."""

DNA_ENCODE_MAP = {"00": "A", "01": "C", "10": "G", "11": "T"}
"""Mapping from two-bit binary strings to DNA bases."""

DNA_DECODE_MAP = {v: k for k, v in DNA_ENCODE_MAP.items()}
"""Reverse mapping from DNA bases back to two-bit binary strings."""


def get_max_homopolymer_length(dna_sequence: str) -> int:
    """Calculates the length of the longest homopolymer in a DNA sequence.

    Args:
        dna_sequence: The DNA sequence string (e.g., "AAATTCGGGG").

    Returns:
        The length of the longest homopolymer. Returns 0 for an empty sequence.
    """
    if not dna_sequence:
        return 0
    dna_sequence = dna_sequence.upper()

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


def check_homopolymer_length(dna_sequence: str, max_len: int) -> bool:
    """Checks if any homopolymer in the DNA sequence exceeds a maximum length."""
    return get_max_homopolymer_length(dna_sequence) > max_len

