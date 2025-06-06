"""Utility constants shared across GeneCoder modules."""

DNA_ENCODE_MAP = {"00": "A", "01": "C", "10": "G", "11": "T"}
"""Mapping from 2-bit binary strings to DNA nucleotides."""

DNA_DECODE_MAP = {v: k for k, v in DNA_ENCODE_MAP.items()}
"""Inverse mapping from DNA nucleotides to 2-bit binary strings."""

__all__ = ["DNA_ENCODE_MAP", "DNA_DECODE_MAP"]

