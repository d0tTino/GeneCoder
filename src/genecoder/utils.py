"""Utility helpers shared across modules."""


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


def check_homopolymer_length(dna_sequence: str, max_len: int) -> bool:
    """Checks if any homopolymer in the DNA sequence exceeds a maximum length."""
    return get_max_homopolymer_length(dna_sequence) > max_len

