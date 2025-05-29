def to_fasta(dna_sequence: str, header: str, line_length: int = 70) -> str:
    """
    Formats a DNA sequence string into a FASTA formatted string.

    Args:
        dna_sequence: A string composed of DNA characters.
        header: The metadata header string for the FASTA sequence.
        line_length: The maximum number of DNA characters per line.
                     Defaults to 70. It is assumed to be a positive integer.

    Returns:
        A string formatted in FASTA style.
    """
    if not isinstance(header, str):
        raise TypeError("Header must be a string.")
    if not isinstance(dna_sequence, str):
        raise TypeError("DNA sequence must be a string.")
    if not isinstance(line_length, int):
        raise TypeError("Line length must be an integer.")

    if line_length <= 0:
        # Or raise ValueError, but for now, treat as no wrapping if non-positive
        # The prompt says "assume line_length will be a positive integer"
        # but a small guard doesn't hurt. Forcing it to a very large number effectively disables wrapping.
        effective_line_length = len(dna_sequence) if len(dna_sequence) > 0 else 70
    else:
        effective_line_length = line_length

    fasta_string = f">{header}\n"

    if not dna_sequence:
        return fasta_string # As per example: ">header\n" for empty sequence

    for i in range(0, len(dna_sequence), effective_line_length):
        fasta_string += dna_sequence[i:i+effective_line_length] + "\n"
    
    return fasta_string
