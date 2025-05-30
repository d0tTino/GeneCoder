def encode_triple_repeat(dna_sequence: str) -> str:
    """Encodes a DNA sequence by repeating each nucleotide three times.

    Args:
        dna_sequence: The DNA sequence string (e.g., "ATGC").

    Returns:
        A new DNA sequence string with each nucleotide tripled (e.g., "AAATTTGGGCC").
    """
    encoded_parts = []
    for nucleotide in dna_sequence:
        encoded_parts.append(nucleotide * 3)
    return "".join(encoded_parts)

def decode_triple_repeat(dna_sequence: str) -> tuple[str, int, int]:
    """Decodes a triple-repeated DNA sequence, correcting single errors in triplets.

    Args:
        dna_sequence: The triple-repeated DNA sequence (e.g., "AAATTTGGGCC" or "AAGTCTGGGCC").

    Returns:
        A tuple containing:
            - corrected_sequence (str): The decoded DNA sequence.
            - corrected_errors (int): Number of triplets where a correction was made.
            - uncorrectable_errors (int): Number of triplets where all bases differed.

    Raises:
        ValueError: If the input sequence length is not a multiple of 3.
    """
    if len(dna_sequence) % 3 != 0:
        raise ValueError("Input DNA sequence length must be a multiple of 3 for triple repeat decoding.")

    if not dna_sequence: # Handle empty sequence input after length check
        return "", 0, 0

    decoded_nucleotides = []
    corrected_errors_count = 0
    uncorrectable_errors_count = 0

    i = 0
    while i < len(dna_sequence):
        triplet = dna_sequence[i:i+3]

        # Count occurrences of each nucleotide in the triplet
        counts = {}
        for nucleotide in triplet:
            counts[nucleotide] = counts.get(nucleotide, 0) + 1

        if len(counts) == 1: # All three are the same (e.g., "AAA")
            decoded_nucleotides.append(triplet[0])
        elif len(counts) == 2: # Two out of three are the same (e.g., "AAG")
            corrected_errors_count += 1
            for nucleotide, count in counts.items():
                if count == 2:
                    decoded_nucleotides.append(nucleotide)
                    break
        else: # All three are different (e.g., "AGC")
            uncorrectable_errors_count += 1
            decoded_nucleotides.append(triplet[0]) # Decode to the first nucleotide

        i += 3

    return "".join(decoded_nucleotides), corrected_errors_count, uncorrectable_errors_count
