"""Encodes and decodes data using a Base-4 Direct Mapping scheme.

In this scheme, each byte of data is directly mapped to four DNA nucleotides.
Each 2-bit segment of a byte corresponds to one nucleotide. The processing
occurs from the Most Significant Bit (MSB) to the Least Significant Bit (LSB)
of each byte.
"""
from typing import Tuple, List, Iterable, Iterator  # For type hints
from genecoder.error_detection import (
    add_parity_to_sequence,
    strip_and_verify_parity,
    PARITY_RULE_GC_EVEN_A_ODD_T
)
from .gc_constrained_encoder import (
    encode_gc_balanced,
    decode_gc_balanced,
    calculate_gc_content,
)
from .utils import get_max_homopolymer_length
from genecoder.error_correction import encode_triple_repeat, decode_triple_repeat
from .utils import DNA_ENCODE_MAP, DNA_DECODE_MAP

__all__ = [
    "encode_base4_direct",
    "decode_base4_direct",
    "encode_gc_balanced",
    "decode_gc_balanced",
    "calculate_gc_content",
    "get_max_homopolymer_length",
    "encode_triple_repeat",
    "decode_triple_repeat",
]

def encode_base4_direct(
    data: bytes | Iterable[bytes],
    add_parity: bool = False,
    k_value: int = 7,
    parity_rule: str = PARITY_RULE_GC_EVEN_A_ODD_T,
    *,
    stream: bool = False,
) -> Iterator[str] | str:
  """Encodes a byte string into a DNA sequence using Base-4 Direct Mapping.

  Optionally, parity nucleotides can be added to the sequence for error detection.

  The mapping from 2-bit binary pairs to DNA nucleotides is as follows:
    - `00` (binary) -> 'A'
    - `01` (binary) -> 'C'
    - `10` (binary) -> 'G'
    - `11` (binary) -> 'T'

  Each input byte (8 bits) is processed by reading its bits in four 2-bit pairs,
  starting from the Most Significant Bit (MSB) pair to the Least Significant Bit 
  (LSB) pair. For example, the byte `0b01000001` (ASCII 'A', decimal 65) is 
  processed as:
    - First 2 bits (MSB): `01` -> 'C'
    - Next 2 bits:        `00` -> 'A'
    - Next 2 bits:        `00` -> 'A'
    - Last 2 bits (LSB):  `01` -> 'C'
  This results in the DNA sequence "CAAC".

  Args:
    data (bytes | Iterable[bytes]): Bytes to encode. When ``stream`` is ``True``
      this should be an iterable yielding chunks of bytes. Otherwise a single
      ``bytes`` object is expected.
    add_parity (bool): If True, add parity nucleotides to the encoded sequence.
                       Defaults to False.
    k_value (int): The size of each data block for parity calculation.
                   Defaults to 7. Must be positive if `add_parity` is True.
    parity_rule (str): The parity rule to use if `add_parity` is True.
                       Defaults to `PARITY_RULE_GC_EVEN_A_ODD_T`.
    stream (bool): If True, return a generator that yields encoded DNA for each
      chunk provided in ``data``.

  Returns:
    Iterator[str] | str: If ``stream`` is ``True`` an iterator yielding DNA
    chunks is returned. Otherwise the full DNA string is returned.
  
  Raises:
    ValueError: If `add_parity` is True and `k_value` is not positive.
    NotImplementedError: If `add_parity` is True and `parity_rule` is unknown.
  """
  def _encode_chunk(chunk: bytes) -> str:
    dna_sequence_parts: list[str] = []
    mapping = {
        0: DNA_ENCODE_MAP["00"],
        1: DNA_ENCODE_MAP["01"],
        2: DNA_ENCODE_MAP["10"],
        3: DNA_ENCODE_MAP["11"],
    }
    for byte_val in chunk:
      pairs = [
          (byte_val >> 6) & 0b11,
          (byte_val >> 4) & 0b11,
          (byte_val >> 2) & 0b11,
          (byte_val >> 0) & 0b11,
      ]
      for pair_val in pairs:
        dna_sequence_parts.append(mapping[pair_val])
    encoded = "".join(dna_sequence_parts)
    if add_parity:
      if k_value <= 0:
        raise ValueError("k_value must be a positive integer when adding parity.")
      encoded = add_parity_to_sequence(encoded, k_value, parity_rule)
    return encoded

  if stream:
    from typing import Iterable as _Iterable
    if isinstance(data, (bytes, bytearray)):
      iterable: _Iterable[bytes] = [data]
    else:
      iterable = data
    return (_encode_chunk(chunk) for chunk in iterable)
  else:
    if not isinstance(data, (bytes, bytearray)):
      data = b"".join(data)
    return _encode_chunk(data)


def decode_base4_direct(
    dna_sequence: str | Iterable[str],
    check_parity: bool = False,
    k_value: int = 7,
    parity_rule: str = PARITY_RULE_GC_EVEN_A_ODD_T,
    *,
    stream: bool = False,
) -> Tuple[bytes, List[int]] | Iterator[Tuple[bytes, List[int]]]:
  """Decodes a DNA sequence string into a byte string using Base-4 Direct Mapping.

  Optionally, this function can check for parity errors if the sequence was
  encoded with parity bits.

  This function reverses the `encode_base4_direct` process. The mapping from
  DNA nucleotides to 2-bit binary pairs is:
    - 'A' -> `00` (binary)
    - 'C' -> `01` (binary)
    - 'G' -> `10` (binary)
    - 'T' -> `11` (binary)

  Each set of 4 DNA characters in the input sequence corresponds to one output byte.
  The first character of a 4-character block maps to the Most Significant Bit 
  (MSB) pair of the resulting byte, and the last character maps to the Least 
  Significant Bit (LSB) pair. For example, the DNA sequence "CAAC" is processed as:
    - 'C' -> `01` (becomes the MSB pair of the byte)
    - 'A' -> `00`
    - 'A' -> `00`
    - 'C' -> `01` (becomes the LSB pair of the byte)
  This results in the byte `0b01000001` (ASCII 'A', decimal 65).

  Args:
    dna_sequence (str | Iterable[str]): DNA sequence to decode. If ``stream`` is
      ``True`` this should be an iterable yielding chunks of the sequence;
      otherwise a single string is expected.
    check_parity (bool): If True, verify parity and report errors.
                         Defaults to False.
    k_value (int): The size of each data block used during parity encoding.
                   Defaults to 7. Must be positive if `check_parity` is True.
    parity_rule (str): The parity rule used during encoding if `check_parity` is True.
                       Defaults to `PARITY_RULE_GC_EVEN_A_ODD_T`.
    stream (bool): If True, return a generator yielding decoded byte chunks for
      each piece provided in ``dna_sequence``.

  Returns:
    Tuple[bytes, List[int]] | Iterator[Tuple[bytes, List[int]]]: If ``stream`` is
    ``True`` an iterator yielding decoded byte chunks and parity error lists is
    returned. Otherwise a single tuple for the full sequence is returned.
      - bytes: The decoded byte string.
      - List[int]: A list of 0-based indices of data blocks where parity
                   errors were detected. Empty if `check_parity` is False
                   or no errors were found.
  
  Raises:
    ValueError: If `check_parity` is True and `k_value` is not positive,
                or if the input sequence (after potential stripping) contains 
                invalid characters or its length is not a multiple of 4.
    NotImplementedError: If `check_parity` is True and `parity_rule` is unknown.
  """
  def _decode_chunk(chunk_seq: str) -> Tuple[bytes, List[int]]:
    parity_errors: List[int] = []
    sequence_to_decode = chunk_seq
    if check_parity:
      if k_value <= 0:
        raise ValueError("k_value must be a positive integer when checking parity.")
      sequence_to_decode, parity_errors = strip_and_verify_parity(
          chunk_seq, k_value, parity_rule
      )
    if not all(c in 'ATCG' for c in sequence_to_decode):
      raise ValueError(
          "Invalid character in sequence to decode. Only 'A', 'T', 'C', 'G' are allowed."
      )
    if len(sequence_to_decode) % 4 != 0:
      raise ValueError(
          "Length of sequence to decode must be a multiple of 4."
      )
    decoded_bytes: list[int] = []
    reverse_mapping = {
        'A': int(DNA_DECODE_MAP['A'], 2),
        'C': int(DNA_DECODE_MAP['C'], 2),
        'G': int(DNA_DECODE_MAP['G'], 2),
        'T': int(DNA_DECODE_MAP['T'], 2),
    }
    for i in range(0, len(sequence_to_decode), 4):
      chars = sequence_to_decode[i:i+4]
      current_byte_val = 0
      current_byte_val |= reverse_mapping[chars[0]] << 6
      current_byte_val |= reverse_mapping[chars[1]] << 4
      current_byte_val |= reverse_mapping[chars[2]] << 2
      current_byte_val |= reverse_mapping[chars[3]] << 0
      decoded_bytes.append(current_byte_val)
    return bytes(decoded_bytes), parity_errors

  if stream:
    from typing import Iterable as _Iterable
    if isinstance(dna_sequence, str):
      iterable: _Iterable[str] = [dna_sequence]
    else:
      iterable = dna_sequence
    return (_decode_chunk(seq) for seq in iterable)
  else:
    if not isinstance(dna_sequence, str):
      dna_sequence = "".join(dna_sequence)
    return _decode_chunk(dna_sequence)
