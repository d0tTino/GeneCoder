"""Implements basic error detection schemes for DNA sequences.

This module provides functions to add parity information to DNA sequences
and to verify it, helping to detect potential errors.
"""
from typing import List, Tuple

# --- Constants for Parity Rules ---
PARITY_RULE_GC_EVEN_A_ODD_T = "GC_even_A_odd_T"
"""Parity Rule: GC_even_A_odd_T.
   - If (count of 'G' + count of 'C') in a block is even, parity bit is 'A'.
   - If (count of 'G' + count of 'C') in a block is odd, parity bit is 'T'.
"""

# --- Helper Functions ---

def _calculate_gc_parity(dna_block: str) -> str:
    """Calculates a parity nucleotide for a DNA block based on G/C count.

    This is a helper for the "GC_even_A_odd_T" parity rule.

    Args:
        dna_block (str): A block of DNA nucleotides.

    Returns:
        str: 'A' if the sum of 'G' and 'C' counts is even, 'T' if odd.
    """
    gc_count = dna_block.count('G') + dna_block.count('C')
    if gc_count % 2 == 0:
        return 'A'  # Even GC count
    else:
        return 'T'  # Odd GC count

# --- Main Parity Functions ---

def add_parity_to_sequence(dna_sequence: str, k_value: int, rule: str) -> str:
    """Adds parity nucleotides to a DNA sequence based on a specified rule.

    The DNA sequence is divided into blocks of `k_value` nucleotides.
    A parity nucleotide is calculated for each block and appended to it.

    Args:
        dna_sequence (str): The original DNA sequence.
        k_value (int): The size of each data block before adding a parity bit.
                       Must be a positive integer.
        rule (str): The parity rule identifier to use. Currently supports
                    `PARITY_RULE_GC_EVEN_A_ODD_T`.

    Returns:
        str: The DNA sequence with interleaved parity nucleotides. Each original
             block of `k_value` nucleotides is followed by one parity nucleotide.

    Raises:
        ValueError: If `k_value` is not a positive integer.
        NotImplementedError: If the specified `rule` is not recognized.
    """
    if not isinstance(k_value, int) or k_value <= 0:
        raise ValueError("k_value must be a positive integer.")

    if not dna_sequence: # If original sequence is empty, return empty
        return ""

    sequence_with_parity_parts: List[str] = []
    
    for i in range(0, len(dna_sequence), k_value):
        data_block = dna_sequence[i:i + k_value]
        parity_nt: str
        if rule == PARITY_RULE_GC_EVEN_A_ODD_T:
            parity_nt = _calculate_gc_parity(data_block)
        else:
            raise NotImplementedError(f"Parity rule '{rule}' is not implemented.")
        
        sequence_with_parity_parts.append(data_block)
        sequence_with_parity_parts.append(parity_nt)
        
    return "".join(sequence_with_parity_parts)


def strip_and_verify_parity(
    dna_sequence_with_parity: str, k_value: int, rule: str
) -> Tuple[str, List[int]]:
    """Strips parity nucleotides and verifies parity for a DNA sequence.

    The function iterates through the sequence in chunks of ``k_value + 1`` –
    each data block followed by its parity nucleotide.  For complete chunks the
    parity nucleotide is recomputed and compared to the stored one.  If the
    final part of the sequence is shorter than ``k_value + 1`` it is assumed to
    contain the last data block and its parity bit.  That last chunk is returned
    as data without verifying its parity.

    Args:
        dna_sequence_with_parity (str): The DNA sequence including interleaved
                                        parity nucleotides.
        k_value (int): The size of each data block (excluding the parity bit).
                       Must be a positive integer.
        rule (str): The parity rule identifier used for encoding. Currently
                    supports `PARITY_RULE_GC_EVEN_A_ODD_T`.

    Returns:
        Tuple[str, List[int]]: A tuple containing:
            - original_sequence (str): The DNA sequence with parity bits removed.
            - parity_error_blocks (List[int]): A list of 0-based indices of
              data blocks where parity errors were detected.

    Raises:
        ValueError: If `k_value` is not a positive integer.
        NotImplementedError: If the specified `rule` is not recognized.
    """
    if not isinstance(k_value, int) or k_value <= 0:
        raise ValueError("k_value must be a positive integer.")

    original_sequence_parts: List[str] = []
    parity_error_blocks: List[int] = []
    chunk_size = k_value + 1

    if rule != PARITY_RULE_GC_EVEN_A_ODD_T:
        raise NotImplementedError(f"Parity rule '{rule}' is not implemented.")

    for block_index, start in enumerate(range(0, len(dna_sequence_with_parity), chunk_size)):
        chunk = dna_sequence_with_parity[start : start + chunk_size]

        data_block = chunk[:-1]
        if len(chunk) == chunk_size:
            read_parity_nt = chunk[-1]
            expected_parity_nt = _calculate_gc_parity(data_block)
            if read_parity_nt != expected_parity_nt:
                parity_error_blocks.append(block_index)
        # For a final chunk shorter than chunk_size we simply strip the last
        # nucleotide as parity without checking it.

        original_sequence_parts.append(data_block)

    return "".join(original_sequence_parts), parity_error_blocks
