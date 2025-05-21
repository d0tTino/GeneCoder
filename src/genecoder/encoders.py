"""Encodes and decodes data using a Base-4 Direct Mapping scheme.

In this scheme, each byte of data is directly mapped to four DNA nucleotides.
Each 2-bit segment of a byte corresponds to one nucleotide. The processing
occurs from the Most Significant Bit (MSB) to the Least Significant Bit (LSB)
of each byte.
"""

def encode_base4_direct(data: bytes) -> str:
  """Encodes a byte string into a DNA sequence using Base-4 Direct Mapping.

  The mapping from 2-bit binary pairs to DNA nucleotides is as follows:
    - `00` (binary) -> 'A'
    - `01` (binary) -> 'T'
    - `10` (binary) -> 'C'
    - `11` (binary) -> 'G'

  Each input byte (8 bits) is processed by reading its bits in four 2-bit pairs,
  starting from the Most Significant Bit (MSB) pair to the Least Significant Bit 
  (LSB) pair. For example, the byte `0b01000001` (ASCII 'A', decimal 65) is 
  processed as:
    - First 2 bits (MSB): `01` -> 'T'
    - Next 2 bits:        `00` -> 'A'
    - Next 2 bits:        `00` -> 'A'
    - Last 2 bits (LSB):  `01` -> 'T'
  This results in the DNA sequence "TAAT".

  Args:
    data (bytes): The byte string to encode.

  Returns:
    str: A string representing the DNA sequence.
  """
  dna_sequence_parts: list[str] = []
  # Mapping of 2-bit integers to DNA characters.
  # 0b00 (0) -> 'A', 0b01 (1) -> 'T', 0b10 (2) -> 'C', 0b11 (3) -> 'G'
  mapping = { 
      0: 'A', 1: 'T', 2: 'C', 3: 'G'
  }

  for byte_val in data:
    # Process bits from most significant to least significant.
    # Each byte is split into four 2-bit segments.
    # Example: byte_val = 0b11001001 (decimal 201)
    # - (byte_val >> 6) & 0b11 results in 0b11 ('G')
    # - (byte_val >> 4) & 0b11 results in 0b00 ('A')
    # - (byte_val >> 2) & 0b11 results in 0b10 ('C')
    # - (byte_val >> 0) & 0b11 results in 0b01 ('T')
    # The resulting DNA sequence for this byte is "GACT".

    # Extract the four 2-bit pairs from the byte.
    pairs = [
        (byte_val >> 6) & 0b11,  # Most significant 2 bits
        (byte_val >> 4) & 0b11,
        (byte_val >> 2) & 0b11,
        (byte_val >> 0) & 0b11   # Least significant 2 bits
    ]

    for pair_val in pairs:
      dna_sequence_parts.append(mapping[pair_val])

  return "".join(dna_sequence_parts)


def decode_base4_direct(dna_sequence: str) -> bytes:
  """Decodes a DNA sequence string into a byte string using Base-4 Direct Mapping.

  This function reverses the `encode_base4_direct` process. The mapping from
  DNA nucleotides to 2-bit binary pairs is:
    - 'A' -> `00` (binary)
    - 'T' -> `01` (binary)
    - 'C' -> `10` (binary)
    - 'G' -> `11` (binary)

  Each set of 4 DNA characters in the input sequence corresponds to one output byte.
  The first character of a 4-character block maps to the Most Significant Bit 
  (MSB) pair of the resulting byte, and the last character maps to the Least 
  Significant Bit (LSB) pair. For example, the DNA sequence "TAAT" is processed as:
    - 'T' -> `01` (becomes the MSB pair of the byte)
    - 'A' -> `00`
    - 'A' -> `00`
    - 'T' -> `01` (becomes the LSB pair of the byte)
  This results in the byte `0b01000001` (ASCII 'A', decimal 65).

  Args:
    dna_sequence (str): The DNA sequence string to decode. Must only contain
      'A', 'T', 'C', 'G' characters, and its length must be a multiple of 4.

  Returns:
    bytes: A byte string representing the original data.

  Raises:
    ValueError: If the input sequence contains invalid characters (not 'A', 'T', 
      'C', 'G') or if its length is not a multiple of 4.
  """
  # Input validation
  if not all(c in 'ATCG' for c in dna_sequence):
    raise ValueError(
        "Invalid character in DNA sequence. Only 'A', 'T', 'C', 'G' are allowed."
    )
  if len(dna_sequence) % 4 != 0:
    raise ValueError("DNA sequence length must be a multiple of 4.")

  decoded_bytes: list[int] = [] 
  # Mapping of DNA characters to their 2-bit integer values.
  # 'A' -> 0b00 (0), 'T' -> 0b01 (1), 'C' -> 0b10 (2), 'G' -> 0b11 (3)
  reverse_mapping = {
      'A': 0, 'T': 1, 'C': 2, 'G': 3
  }

  for i in range(0, len(dna_sequence), 4):
    chars = dna_sequence[i:i+4] # Get a 4-character block
    current_byte_val = 0
    # Convert the 4 DNA characters back into one byte.
    # Example: chars = "GACT" (G=0b11, A=0b00, C=0b10, T=0b01)
    # - 'G' (0b11) shifted left by 6 bits: 0b11000000
    # - 'A' (0b00) shifted left by 4 bits: 0b00000000
    # - 'C' (0b10) shifted left by 2 bits: 0b00001000
    # - 'T' (0b01) shifted left by 0 bits: 0b00000001
    # Resulting byte: 0b11000000 | 0b00000000 | 0b00001000 | 0b00000001 = 0b11001001 (201)

    current_byte_val |= reverse_mapping[chars[0]] << 6 # 1st char is MSB pair
    current_byte_val |= reverse_mapping[chars[1]] << 4
    current_byte_val |= reverse_mapping[chars[2]] << 2
    current_byte_val |= reverse_mapping[chars[3]] << 0 # 4th char is LSB pair
    decoded_bytes.append(current_byte_val)

  return bytes(decoded_bytes)
