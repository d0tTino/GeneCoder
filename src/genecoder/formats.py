"""Provides functions for formatting data into and parsing data from FASTA format.

FASTA is a text-based format for representing nucleotide sequences or peptide
sequences, where nucleotides or amino acids are represented using single-letter
codes. A sequence in FASTA format consists of a single-line description (header),
followed by lines of sequence data.
"""
from typing import List, Tuple # For type hints

def to_fasta(dna_sequence: str, header: str, line_width: int = 60) -> str:
    """Formats a DNA sequence into a FASTA formatted string.

    Args:
        dna_sequence (str): The DNA sequence string (e.g., "ATGC...").
        header (str): The header string for the FASTA sequence, which will be
            prefixed with ">". Do not include ">" in this argument.
        line_width (int): The maximum number of characters per line for the 
            sequence data. Defaults to 60. Must be a positive integer.

    Returns:
        str: A string representing the DNA sequence in FASTA format.
             Each line of the sequence, including the last, is followed by a
             newline character. An empty sequence results in only the header
             line followed by a newline.

    Raises:
        ValueError: If `line_width` is not a positive integer.
    """
    if not isinstance(line_width, int) or line_width <= 0:
        raise ValueError("line_width must be a positive integer.")

    fasta_string = f">{header}\n"
    
    if not dna_sequence: # Handle empty sequence explicitly for clarity
        return fasta_string

    for i in range(0, len(dna_sequence), line_width):
        fasta_string += dna_sequence[i:i+line_width] + "\n"
        
    return fasta_string


def from_fasta(fasta_content: str) -> List[Tuple[str, str]]:
    """Parses content in FASTA format and extracts sequence records.

    A FASTA record consists of a header line starting with ">" followed by
    one or more lines of sequence data. This function can parse multiple
    FASTA records from a single string input. Lines not part of a valid
    record structure (e.g., text before the first header) are ignored.

    Sequence lines are processed by first stripping leading/trailing whitespace,
    then removing all internal whitespace before concatenation. For example,
    a line "  AT GC  " becomes "ATGC".

    Args:
        fasta_content (str): A string containing the entire FASTA formatted data.

    Returns:
        List[Tuple[str, str]]: A list of tuples, where each tuple contains 
        `(header, sequence)`.
        - `header` (str): The header string (content after the initial ">", 
          stripped of leading/trailing whitespace).
        - `sequence` (str): The concatenated sequence data, with all internal
          whitespace removed from each original sequence line.
        Returns an empty list if no valid FASTA records (lines starting with ">")
        are found.
    
    Example:
        >>> fasta_data = ">seq1 description1\\nAT GC\\nCGTA\\n>seq2\\nTT TT\\nAAAA"
        >>> from_fasta(fasta_data)
        [('seq1 description1', 'ATGCCGTA'), ('seq2', 'TTTTAAAA')]
    """
    records: List[Tuple[str, str]] = []
    current_header: str | None = None
    current_sequence_parts: List[str] = []

    lines = fasta_content.splitlines()

    for line_text in lines: # Renamed 'line' to 'line_text' for clarity
        stripped_line = line_text.strip()
        if not stripped_line: # Skip empty or whitespace-only lines
            continue

        if stripped_line.startswith(">"):
            # If a previous record was being processed, finalize and save it.
            if current_header is not None:
                records.append((current_header, "".join(current_sequence_parts)))
            
            current_header = stripped_line[1:].strip() # Store header without ">"
            current_sequence_parts = [] # Reset for the new sequence
        elif current_header is not None: 
            # This is a sequence line for the current active header.
            # Remove all whitespace (leading, trailing, and internal) from the sequence line.
            processed_sequence_line = "".join(stripped_line.split())
            current_sequence_parts.append(processed_sequence_line)
        # else: If line_text does not start with ">" and no current_header is active,
        #       it's considered content outside a valid FASTA record (e.g., text
        #       before the first header) and is ignored.

    # After the loop, save the last processed record, if any.
    if current_header is not None:
        records.append((current_header, "".join(current_sequence_parts)))

    return records
