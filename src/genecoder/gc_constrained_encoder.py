"""Encoding helpers with GC content and homopolymer constraints.

This module provides utility functions to measure GC content and
homopolymer runs as well as a lightweight encoder/decoder pair that
wraps :mod:`genecoder.encoders`.  The ``encode_gc_balanced`` function
encodes binary data using ``encode_base4_direct`` while ensuring the
result meets simple constraints.  ``decode_gc_balanced`` reverses the
process and can optionally validate those constraints on the decoded
sequence.

Dependencies
------------
The functions import :mod:`genecoder.encoders` locally to avoid
circular imports.  Only the Python standard library is otherwise
required.
"""

from typing import Optional, Tuple, cast
import logging

from .utils import check_homopolymer_length, get_max_homopolymer_length

logger = logging.getLogger(__name__)

# Recommended default constraints used by the CLI and other helpers.  These
# values are exposed so callers can reference a single source of truth when
# evaluating GC content and homopolymer runs.
DEFAULT_GC_MIN = 0.45
DEFAULT_GC_MAX = 0.55
DEFAULT_MAX_HOMOPOLYMER = 3

GC_BALANCED_MAPS = [
    {"00": "A", "01": "C", "10": "G", "11": "T"},
    {"00": "A", "01": "C", "10": "T", "11": "G"},
    {"00": "C", "01": "A", "10": "G", "11": "T"},
    {"00": "C", "01": "A", "10": "T", "11": "G"},
]

GC_BALANCED_DECODE_MAPS = [
    {v: k for k, v in mapping.items()} for mapping in GC_BALANCED_MAPS
]


def check_default_constraints(
    dna_sequence: str, suppress_warnings: bool = False
) -> tuple[float, int, bool, bool]:
    """Return GC/HP metrics and flags indicating violations of defaults.

    Parameters
    ----------
    dna_sequence:
        Sequence to analyse.
    suppress_warnings:
        When ``True`` no warnings are logged even if the defaults are
        exceeded.  The caller is expected to consult the boolean flags in the
        returned tuple.

    Returns
    -------
    Tuple consisting of ``(gc_content, max_homopolymer, gc_violation,
    homopolymer_violation)``.
    """

    gc_val = calculate_gc_content(dna_sequence)
    hp_val = get_max_homopolymer_length(dna_sequence)
    gc_bad = gc_val < DEFAULT_GC_MIN or gc_val > DEFAULT_GC_MAX
    hp_bad = hp_val > DEFAULT_MAX_HOMOPOLYMER

    if not suppress_warnings:
        if gc_bad:
            logger.warning(
                "GC content %.2f%% outside recommended range [%.2f%%, %.2f%%]",
                gc_val * 100,
                DEFAULT_GC_MIN * 100,
                DEFAULT_GC_MAX * 100,
            )
        if hp_bad:
            logger.warning(
                "Max homopolymer length %d exceeds recommended limit %d",
                hp_val,
                DEFAULT_MAX_HOMOPOLYMER,
            )

    return gc_val, hp_val, gc_bad, hp_bad

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


def encode_gc_balanced(
    data: bytes, target_gc_min: float, target_gc_max: float, max_homopolymer: int
) -> str:
    """Encodes binary data into a DNA sequence with GC content and homopolymer constraints.

    Encoding Strategy:
    - Encodes data using `encode_base4_direct`.
    - If constraints (GC content, homopolymer length) are met, returns the sequence prefixed with "0".
    - If constraints are violated, inverts data bits and re-encodes.
      The alternative sequence is also checked against the constraints. If it
      still violates them, the sequence is returned prefixed with "1" and a
      warning is logged.


    Args:
        data: The binary data to encode.
        target_gc_min: The minimum target GC content.
        target_gc_max: The maximum target GC content.
        max_homopolymer: The maximum allowed homopolymer length.

    Returns:
        The encoded DNA sequence as a string, prefixed with "0" or "1".
    """
    from .encoders import encode_base4_direct  # Local import to avoid circular dependency

    if target_gc_min > target_gc_max:
        raise ValueError("target_gc_min cannot be greater than target_gc_max")
    if max_homopolymer < 1:
        raise ValueError("max_homopolymer must be at least 1")

    if not data:
        return "0"

    def _constraints_ok(sequence: str) -> bool:
        return (
            target_gc_min <= calculate_gc_content(sequence) <= target_gc_max
            and not check_homopolymer_length(sequence, max_homopolymer)
        )

    modified_data = bytes(b ^ 0xFF for b in data)

    for idx, mapping in enumerate(GC_BALANCED_MAPS):
        initial_sequence = cast(
            str, encode_base4_direct(data, add_parity=False, encode_map=mapping)
        )
        if _constraints_ok(initial_sequence):
            return f"0{idx}" + initial_sequence

        alternative_sequence = cast(
            str,
            encode_base4_direct(modified_data, add_parity=False, encode_map=mapping),
        )
        if _constraints_ok(alternative_sequence):
            return f"1{idx}" + alternative_sequence

    for mask in range(1, 255):
        masked_data = bytes(b ^ mask for b in data)
        for idx, mapping in enumerate(GC_BALANCED_MAPS):
            candidate_sequence = cast(
                str,
                encode_base4_direct(masked_data, add_parity=False, encode_map=mapping),
            )
            if _constraints_ok(candidate_sequence):
                return f"2{idx}{mask:03d}" + candidate_sequence

    logger.warning(
        "Inverted sequence violates GC content or homopolymer constraints"
    )
    fallback_mapping = GC_BALANCED_MAPS[0]
    fallback_sequence = cast(
        str, encode_base4_direct(modified_data, add_parity=False, encode_map=fallback_mapping)
    )
    return "10" + fallback_sequence

def decode_gc_balanced(
    dna_sequence: str,
    expected_gc_min: Optional[float] = None,
    expected_gc_max: Optional[float] = None,
    expected_max_homopolymer: Optional[int] = None
) -> bytes:
    """Decodes a DNA sequence (encoded by encode_gc_balanced) back into binary data.

    Optionally, expected constraints can be provided and are enforced during
    decoding; violations raise ``ValueError``.

    Decoding Strategy:
    - Checks the first character (signal bit).
    - If "0", decodes the rest of the sequence directly.
    - If "1", decodes the rest, then inverts the bits of the result.

    Args:
        dna_sequence: The DNA sequence to decode.
        expected_gc_min: The expected minimum GC content to enforce.
        expected_gc_max: The expected maximum GC content to enforce.
        expected_max_homopolymer: The expected maximum homopolymer length to enforce.

    Returns:
        The decoded binary data.

    Raises:
        ValueError: If the sequence is too short, the signal bit is invalid,
            or the GC/homopolymer constraints are violated.
    """
    # The expected constraint inputs are enforced after decoding by recomputing
    # GC content and homopolymer length on the payload and raising ValueError
    # if any expected bound is violated.

    if not dna_sequence or len(dna_sequence) < 1:  # Sequence must have at least signal bit
        raise ValueError("Input DNA sequence is too short to decode (missing signal bit).")

    if dna_sequence == "0":
        return b""

    from .encoders import decode_base4_direct  # Local import to avoid circular dependency

    # The first nucleotide acts as a signal bit. ``"0"`` means the sequence is
    # the direct encoding of the original data, while ``"1"`` indicates that the
    # data bytes were bitwise inverted before encoding.  Everything after the
    # first character is the actual payload.
    signal_bit = dna_sequence[0]
    payload_dna_sequence = dna_sequence[1:]
    map_index = 0
    if payload_dna_sequence and payload_dna_sequence[0].isdigit():
        map_index = int(payload_dna_sequence[0])
        payload_dna_sequence = payload_dna_sequence[1:]
    if map_index >= len(GC_BALANCED_DECODE_MAPS):
        raise ValueError(f"Invalid map index: {map_index}.")

    if not payload_dna_sequence:  # Check if after removing signal bit, sequence is empty
        raise ValueError("Input DNA sequence is too short (only signal bit found, no payload).")

    if signal_bit == "2":
        if len(payload_dna_sequence) < 3 or not payload_dna_sequence[:3].isdigit():
            raise ValueError("Masked sequence missing XOR key")
        mask = int(payload_dna_sequence[:3])
        payload_dna_sequence = payload_dna_sequence[3:]
        decoded_tuple = decode_base4_direct(
            payload_dna_sequence,
            check_parity=False,
            decode_map=GC_BALANCED_DECODE_MAPS[map_index],
        )
        temp_decoded_data = cast(Tuple[bytes, list[int]], decoded_tuple)[0]
        decoded_data = bytes(b ^ mask for b in temp_decoded_data)
    elif signal_bit == "0":
        decoded_tuple = decode_base4_direct(
            payload_dna_sequence,
            check_parity=False,
            decode_map=GC_BALANCED_DECODE_MAPS[map_index],
        )
        decoded_data = cast(Tuple[bytes, list[int]], decoded_tuple)[0]
    elif signal_bit == "1":
        decoded_tuple = decode_base4_direct(
            payload_dna_sequence,
            check_parity=False,
            decode_map=GC_BALANCED_DECODE_MAPS[map_index],
        )
        temp_decoded_data = cast(Tuple[bytes, list[int]], decoded_tuple)[0]
        decoded_data = bytes(b ^ 0xFF for b in temp_decoded_data)
    else:
        raise ValueError(
            f"Invalid signal bit: '{signal_bit}'. Expected '0', '1', or '2'."
        )

    # Recalculate constraints on the payload so the caller can optionally check
    # that the received sequence still satisfies them.
    gc_content = calculate_gc_content(payload_dna_sequence)
    max_homopolymer_len = get_max_homopolymer_length(payload_dna_sequence)

    if expected_gc_min is not None and gc_content < expected_gc_min:
        raise ValueError(
            f"GC content {gc_content:.2%} below expected minimum {expected_gc_min:.2%}"
        )
    if expected_gc_max is not None and gc_content > expected_gc_max:
        raise ValueError(
            f"GC content {gc_content:.2%} above expected maximum {expected_gc_max:.2%}"
        )
    if (
        expected_max_homopolymer is not None
        and max_homopolymer_len > expected_max_homopolymer
    ):
        raise ValueError(
            "Longest homopolymer length "
            f"{max_homopolymer_len} exceeds expected maximum {expected_max_homopolymer}"
        )

    return decoded_data
