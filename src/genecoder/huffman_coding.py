"""Implements Huffman coding for byte data and its conversion to/from DNA sequences.

This module provides functions to:
1.  Calculate byte frequencies in input data.
2.  Build a Huffman tree and generate Huffman codes (binary strings) for each byte.
3.  Encode input byte data into a DNA sequence using the generated Huffman codes
    and a subsequent 2-bit-per-nucleotide mapping.
4.  Decode a DNA sequence back to the original byte data, given the Huffman
    table and padding information.
"""
import collections
import heapq
from typing import Dict, Tuple, List, Union # For type hints within _generate_codes_from_tree

# Type alias for Huffman tree nodes used internally
HuffmanNode = Union[int, List[Union[int, 'HuffmanNode', List['HuffmanNode']]]] # type: ignore

# --- Helper Functions ---

def _calculate_frequencies(data: bytes) -> collections.Counter:
    """Calculates the frequency of each byte in the input data.

    Args:
        data (bytes): The byte string to analyze.

    Returns:
        collections.Counter: A counter mapping each byte (as an int from 0-255)
        to its frequency. Returns an empty Counter if input data is empty.
    """
    if not data:
        return collections.Counter()
    return collections.Counter(data)

def _build_huffman_tree_and_codes(frequencies: collections.Counter) -> Dict[int, str]:
    """Builds a Huffman tree from byte frequencies and generates Huffman codes.

    Args:
        frequencies (collections.Counter): A Counter object mapping byte values
            (int) to their frequencies.

    Returns:
        Dict[int, str]: A dictionary mapping each byte value (int) to its
        Huffman code (a binary string). Returns an empty dictionary if
        frequencies are empty.
    """
    if not frequencies:
        return {}

    # Use a unique ID from a counter to ensure stable sorting in heapq for
    # nodes that might have the same frequency. This makes tree construction
    # deterministic for tie-breaking.
    unique_id_counter = 0
    
    # The heap stores tuples: (frequency, unique_id, node).
    # 'node' is an int for leaf nodes (representing the byte value) or a 
    # list [left_child, right_child] for internal nodes.
    heap: List[Tuple[int, int, HuffmanNode]] = []
    for byte_val, freq in frequencies.items():
        heapq.heappush(heap, (freq, unique_id_counter, byte_val))
        unique_id_counter += 1

    # Edge case: If there's only one unique byte in the input data.
    # The Huffman code for this single byte is defined as '0'.
    if len(heap) == 1:
        _freq, _uid, byte_val = heap[0]
        # Ensure byte_val is an int, as expected by type hints, not a list.
        if isinstance(byte_val, int):
            return {byte_val: '0'}
        else:
            # This case should ideally not be reached if frequencies are from bytes.
            # However, for robustness, handle potential malformed heap item.
            raise ValueError("Malformed heap item for single unique byte.")


    # Build the Huffman tree by repeatedly combining the two lowest-frequency nodes.
    while len(heap) > 1:
        freq1, uid1, left_node = heapq.heappop(heap)
        freq2, uid2, right_node = heapq.heappop(heap)

        new_freq = freq1 + freq2
        # Internal nodes are represented as a list: [left_child, right_child]
        internal_node: HuffmanNode = [left_node, right_node] 
        
        heapq.heappush(heap, (new_freq, unique_id_counter, internal_node))
        unique_id_counter += 1
    
    # The last remaining item on the heap is the root of the Huffman tree.
    # heap[0][2] directly accesses the node part of the tuple.
    root_node_wrapper = heap[0][2] 
    
    codes_dict: Dict[int, str] = {}

    # Recursive helper function to traverse the tree and generate codes.
    def _generate_codes_from_tree(node: HuffmanNode, current_code: str) -> None:
        """Recursively traverses the Huffman tree to generate binary codes.

        Args:
            node (HuffmanNode): The current node in the Huffman tree.
                An int for a leaf (byte value) or a list for an internal node.
            current_code (str): The binary code accumulated so far for this path.
        """
        if isinstance(node, int):  # Leaf node (byte value)
            # Assign the accumulated code. If the tree has only one node (single unique byte),
            # its code is '0' (handled by the `if len(heap) == 1` case).
            # This path handles cases where current_code is empty for a single node root,
            # which shouldn't happen if len(heap) == 1 is handled correctly.
            codes_dict[node] = current_code if current_code else "0"
            return
        
        # Internal node: node is expected to be [left_child, right_child]
        if isinstance(node, list) and len(node) == 2:
            _generate_codes_from_tree(node[0], current_code + '0')  # Left child gets '0'
            _generate_codes_from_tree(node[1], current_code + '1')  # Right child gets '1'
        # else: Malformed internal node, ideally raise error or log.
        #       For now, assumes valid tree structure from heap construction.

    # Generate codes only if the root is a tree (list structure).
    # If frequencies contained only one item, root_node_wrapper would be an int,
    # and that case is handled by `if len(heap) == 1`, which returns directly.
    if isinstance(root_node_wrapper, list):
        _generate_codes_from_tree(root_node_wrapper, "")
    # If root_node_wrapper is an int here, it implies an issue, as the single-item
    # case should have returned. An empty `frequencies` also returns early.
    
    return codes_dict

# --- Main Encoding Function ---

def encode_huffman(data: bytes) -> Tuple[str, Dict[int, str], int]:
    """Encodes a byte string using Huffman coding and maps to a DNA sequence.

    The process involves:
    1.  Calculating byte frequencies in the input data.
    2.  Building a Huffman tree based on these frequencies.
    3.  Generating Huffman codes (variable-length binary strings) for each byte.
    4.  Concatenating the Huffman codes for each byte in the input data to form
        a single binary string.
    5.  Padding this binary string with '0's at the end, if necessary, to ensure
        its length is a multiple of 2 (for 2-bit DNA mapping). The number of
        padding bits added (0 or 1) is recorded.
    6.  Converting the padded binary string into a DNA sequence, where each
        2-bit pair is mapped to a nucleotide:
          - "00" -> 'A'
          - "01" -> 'T'
          - "10" -> 'C'
          - "11" -> 'G'

    Args:
        data (bytes): The byte string to encode.

    Returns:
        Tuple[str, Dict[int, str], int]: A tuple containing:
            - dna_sequence (str): The final DNA sequence.
            - huffman_table (Dict[int, str]): A dictionary mapping each original 
              byte (as an integer) to its Huffman code (binary string).
            - num_padding_bits (int): The number of '0' bits added to the end 
              of the binary string before DNA conversion (0 or 1).
    """
    if not data:
        return ("", {}, 0)

    frequencies = _calculate_frequencies(data)
    huffman_table = _build_huffman_tree_and_codes(frequencies)

    # Construct the single binary string from Huffman codes.
    # If data contains a byte not in huffman_table (e.g., empty data led to empty table),
    # this would error. However, `if not data` handles empty data.
    # If huffman_table is empty due to empty frequencies from non-empty data (should not happen),
    # it would also error here.
    encoded_binary_string_list = [huffman_table[byte_val] for byte_val in data]
    encoded_binary_string = "".join(encoded_binary_string_list)
    
    # Determine number of padding bits needed (0 or 1) for 2-bit DNA mapping.
    num_padding_bits = (2 - len(encoded_binary_string) % 2) % 2
    padded_encoded_binary_string = encoded_binary_string + ('0' * num_padding_bits)

    # Convert the padded binary string to a DNA sequence.
    dna_sequence_parts: List[str] = []
    dna_mapping = {"00": 'A', "01": 'T', "10": 'C', "11": 'G'}

    # This check covers cases where data was non-empty but resulted in an empty
    # encoded_binary_string (e.g., if all Huffman codes were empty strings, which
    # is not standard for Huffman coding but robustly handled).
    if not padded_encoded_binary_string: 
        return "", huffman_table, num_padding_bits # Should align with empty data output

    for i in range(0, len(padded_encoded_binary_string), 2):
        two_bits = padded_encoded_binary_string[i:i+2]
        # Padding ensures len(two_bits) is always 2 if padded_encoded_binary_string is not empty.
        dna_sequence_parts.append(dna_mapping[two_bits])

    dna_sequence = "".join(dna_sequence_parts)

    return dna_sequence, huffman_table, num_padding_bits


# --- Main Decoding Function ---

def decode_huffman(dna_sequence: str, huffman_table: Dict[int, str], num_padding_bits: int) -> bytes:
    """Decodes a Huffman-encoded DNA sequence back into the original byte string.

    The process involves:
    1.  Converting the DNA sequence back into its binary string representation 
        using the mapping: 'A' -> "00", 'T' -> "01", 'C' -> "10", 'G' -> "11".
    2.  Removing any padding bits from the end of the binary string, based on 
        `num_padding_bits`.
    3.  Inverting the provided `huffman_table` to map binary codes back to 
        original byte values.
    4.  Iterating through the unpadded binary string, matching prefixes against 
        the inverted Huffman codes to reconstruct the original bytes.

    Args:
        dna_sequence (str): The DNA sequence string to decode.
        huffman_table (Dict[int, str]): A dictionary mapping each original byte 
            (as an integer) to its Huffman code (binary string). This is the 
            same table returned by the `encode_huffman` function.
        num_padding_bits (int): The number of '0' bits that were added as 
            padding during encoding (0 or 1). This is also returned by 
            `encode_huffman`.

    Returns:
        bytes: A byte string representing the original data.

    Raises:
        ValueError:
            - If `dna_sequence` contains invalid characters (not 'A', 'T', 'C', 
              or 'G').
            - If `num_padding_bits` is inconsistent (e.g., negative, or more 
              padding than bits available, or padded bits are not '0').
            - If the parameters suggest an empty input but are inconsistent 
              (e.g., non-empty table with empty sequence).
            - If the binary string (after unpadding) contains sequences that do 
              not match any code in the `huffman_table` (indicating corruption 
              or incorrect table).
            - If, after successfully decoding some bytes, there are remaining 
              bits in the binary string that do not form a complete, valid 
              Huffman code.
    """
    # Handle consistent empty input: empty sequence, empty table, zero padding.
    if not dna_sequence and not huffman_table and num_padding_bits == 0:
        return b""

    # 1. Convert DNA sequence to its binary string representation.
    binary_digits_list: List[str] = []
    dna_to_binary_map = {'A': "00", 'T': "01", 'C': "10", 'G': "11"}
    for char_dna in dna_sequence:
        binary_pair = dna_to_binary_map.get(char_dna)
        if binary_pair is None:
            raise ValueError(f"Invalid DNA character '{char_dna}' in sequence.")
        binary_digits_list.append(binary_pair)
    encoded_binary_string = "".join(binary_digits_list)

    # Handle if DNA conversion results in an empty binary string.
    if not encoded_binary_string:
        # If also consistent with empty input parameters, return empty bytes.
        if not huffman_table and num_padding_bits == 0: 
            return b""
        # Otherwise, it's an inconsistency (e.g., non-empty DNA was all invalid chars,
        # or empty DNA with a non-empty table).
        raise ValueError(
            "Empty binary string derived from DNA, but Huffman table or padding "
            "suggests data was expected."
        )

    # 2. Remove padding bits.
    unpadded_binary_string: str
    if num_padding_bits < 0:
        raise ValueError("num_padding_bits cannot be negative.")
    if num_padding_bits > 0:
        if num_padding_bits > len(encoded_binary_string):
            raise ValueError(
                f"Invalid padding: {num_padding_bits} padding bits claimed, but "
                f"only {len(encoded_binary_string)} bits available."
            )
        # Verify that the actual padding bits are all '0'.
        padding_actual = encoded_binary_string[-num_padding_bits:]
        if padding_actual != '0' * num_padding_bits:
            raise ValueError(
                f"Invalid padding bits: expected all '0's but found '{padding_actual}'."
            )
        unpadded_binary_string = encoded_binary_string[:-num_padding_bits]
    else: # num_padding_bits == 0
        unpadded_binary_string = encoded_binary_string


    # Handle if unpadded binary string is empty.
    if not unpadded_binary_string:
        # If the Huffman table is also empty, it's consistent with empty original data.
        if not huffman_table: 
            return b""
        # If table is not empty, it's an inconsistency (e.g. original data was one
        # unique byte like 'A', its code '0', padded to '00'. If num_padding_bits
        # was then given as 2, unpadded becomes empty, but table {'A':'0'} exists).
        # This implies all original data was represented by bits that were then
        # considered padding.
        raise ValueError(
            "Unpadded binary string is empty, but Huffman table is not empty, "
            "implying all data was removed as padding."
        )

    # 3. Invert the Huffman table for decoding.
    # Maps: binary code (str) -> original byte value (int)
    try:
        # Ensure huffman_table.items() can be iterated over (i.e., it's a dict)
        inverted_huffman_table = {
            code: byte_val for byte_val, code in huffman_table.items()
        }
    except AttributeError: # .items() failed
        raise ValueError("Invalid huffman_table format: must be a dictionary.")

    if not inverted_huffman_table: # Should not happen if unpadded_binary_string is not empty
        raise ValueError(
            "Huffman table is effectively empty for decoding, but there is data."
        )

    # 4. Decode the unpadded binary string to bytes.
    decoded_bytes_list: List[bytes] = []
    current_code_buffer = [] # Use list of chars for efficient joining
    for bit in unpadded_binary_string:
        current_code_buffer.append(bit)
        current_prefix = "".join(current_code_buffer)
        if current_prefix in inverted_huffman_table:
            byte_val = inverted_huffman_table[current_prefix]
            decoded_bytes_list.append(bytes([byte_val]))
            current_code_buffer = [] # Reset buffer
    
    # If there are remaining bits in the buffer, they don't form a valid code.
    if current_code_buffer: 
        raise ValueError(
            f"Corrupted data or incorrect Huffman table: "
            f"remaining unparsed bits '{"".join(current_code_buffer)}'."
        )

    return b"".join(decoded_bytes_list)
