"""Utility helpers shared across modules."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

DNA_ENCODE_MAP = {"00": "A", "01": "C", "10": "G", "11": "T"}
"""Mapping from two-bit binary strings to DNA bases (Base-4 alphabet)."""

DNA_DECODE_MAP = {v: k for k, v in DNA_ENCODE_MAP.items()}
"""Reverse mapping from DNA bases back to two-bit binary strings."""

ALPHABETS: dict[str, str] = {
    "base4": "ACGT",
    "base5": "ACGTN",
    "base6": "ACGTRY",
}
"""Supported nucleotide alphabets for encoding."""


def get_temp_dir() -> Path:
    """Return the directory used for temporary files."""

    return Path(os.getenv("GENECODER_TMP", tempfile.gettempdir()))


def get_alphabet_maps(alphabet: str) -> tuple[dict[str, str], dict[str, str]]:
    """Return encode/decode maps for the selected alphabet."""
    if alphabet not in ALPHABETS:
        raise ValueError(f"Unknown alphabet '{alphabet}'")
    letters = ALPHABETS[alphabet]
    encode_map = {
        "00": letters[0],
        "01": letters[1],
        "10": letters[2],
        "11": letters[3],
    }
    decode_map = {v: k for k, v in encode_map.items()}
    return encode_map, decode_map


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


def bit_error_rate(original: bytes, recovered: bytes) -> float:
    """Return the bit error rate between two byte strings."""
    total_bits = len(original) * 8
    min_len = min(len(original), len(recovered))
    errors = 0
    for o, r in zip(original[:min_len], recovered[:min_len]):
        errors += (o ^ r).bit_count()
    if len(recovered) < len(original):
        errors += (len(original) - len(recovered)) * 8
    return errors / total_bits if total_bits else 0.0

