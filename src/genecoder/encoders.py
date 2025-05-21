def encode_base4_direct(data: bytes) -> str:
  """
  Encodes a byte string into a DNA sequence using Base-4 Direct Mapping.

  Each byte (8 bits) is processed by taking 2 bits at a time (4 pairs per byte).
  Each 2-bit pair is mapped to a DNA nucleotide:
    - 00 -> A
    - 01 -> T
    - 10 -> C
    - 11 -> G

  Args:
    data: The byte string to encode.

  Returns:
    A string representing the DNA sequence.
  """
  dna_sequence = []
  mapping = {
      0b00: 'A',  # 0
      0b01: 'T',  # 1
      0b10: 'C',  # 2
      0b11: 'G'   # 3
  }

  for byte in data:
    # Process bits from most significant to least significant
    # Extract 4 pairs of 2 bits from each byte
    # Example: byte = 0b11001001
    # 1st pair: (byte >> 6) & 0b11  (11001001 >> 6 = 00000011; 00000011 & 11 = 11) -> G
    # 2nd pair: (byte >> 4) & 0b11  (11001001 >> 4 = 00001100; 00001100 & 11 = 00) -> A
    # 3rd pair: (byte >> 2) & 0b11  (11001001 >> 2 = 00110010; 00110010 & 11 = 10) -> C
    # 4th pair: (byte >> 0) & 0b11  (11001001 >> 0 = 11001001; 11001001 & 11 = 01) -> T
    # Result for 0b11001001 (201) should be "GACT"

    pairs = [
        (byte >> 6) & 0b11,  # Most significant 2 bits
        (byte >> 4) & 0b11,
        (byte >> 2) & 0b11,
        (byte >> 0) & 0b11   # Least significant 2 bits
    ]

    for pair_val in pairs:
      dna_sequence.append(mapping[pair_val])

  return "".join(dna_sequence)


def decode_base4_direct(dna_sequence: str) -> bytes:
  """
  Decodes a DNA sequence string into a byte string using Base-4 Direct Mapping.

  Each set of 4 DNA characters is converted back into one byte (8 bits).
  The mapping from DNA nucleotide to 2-bit pairs is:
    - 'A' -> 00
    - 'T' -> 01
    - 'C' -> 10
    - 'G' -> 11

  Args:
    dna_sequence: The DNA sequence string to decode.

  Returns:
    A byte string representing the original data.

  Raises:
    ValueError: If the input sequence contains invalid characters
                or if its length is not a multiple of 4.
  """
  if not all(c in 'ATCG' for c in dna_sequence):
    raise ValueError("Invalid character in DNA sequence. Only 'A', 'T', 'C', 'G' are allowed.")

  if len(dna_sequence) % 4 != 0:
    raise ValueError("DNA sequence length must be a multiple of 4.")

  byte_list = []
  reverse_mapping = {
      'A': 0b00,
      'T': 0b01,
      'C': 0b10,
      'G': 0b11
  }

  for i in range(0, len(dna_sequence), 4):
    chars = dna_sequence[i:i+4]
    byte_val = 0
    # Example: chars = "GACT"
    # 'G' (11) << 6 = 11000000
    # 'A' (00) << 4 = 00000000
    # 'C' (10) << 2 = 00001000
    # 'T' (01) << 0 = 00000001
    # byte_val = 11000000 | 00000000 | 00001000 | 00000001 = 11001001 (201)

    byte_val |= reverse_mapping[chars[0]] << 6
    byte_val |= reverse_mapping[chars[1]] << 4
    byte_val |= reverse_mapping[chars[2]] << 2
    byte_val |= reverse_mapping[chars[3]] << 0
    byte_list.append(byte_val)

  return bytes(byte_list)
