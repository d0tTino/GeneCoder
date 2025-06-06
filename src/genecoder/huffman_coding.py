"""Implements Huffman coding for byte data and its conversion to/from DNA sequences.

This module provides functions to:
1.  Calculate byte frequencies in input data.
2.  Build a Huffman tree and generate Huffman codes (binary strings) for each byte.
3.  Encode input byte data into a DNA sequence using the generated Huffman codes
    and a subsequent 2-bit-per-nucleotide mapping.
4.  Decode a DNA sequence back to the original byte data, given the Huffman
    table and padding information.
5.  Optionally, add and check parity bits for basic error detection with Huffman-encoded sequences.
"""
import collections
import heapq
from typing import Dict, Tuple, List, Union # For type hints
from .utils import DNA_ENCODE_MAP, DNA_DECODE_MAP
from genecoder.error_detection import (
    add_parity_to_sequence, 
    strip_and_verify_parity, 
    PARITY_RULE_GC_EVEN_A_ODD_T
)

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

    # heapq only guarantees a stable order for the first element of the tuple
    # it sorts on.  When multiple bytes share the same frequency we still want
    # deterministic behaviour.  To achieve this a monotonically increasing
    # ``unique_id_counter`` is pushed as the second element of the tuple.  It
    # does not affect the Huffman algorithm itself but ensures that ties are
    # resolved consistently across runs.
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


    # Build the Huffman tree by repeatedly combining the two lowest-frequency
    # nodes.  ``heapq`` ensures we always pop the nodes with the smallest
    # frequency (and, because of the unique id, gives deterministic results when
    # frequencies are equal).
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

def encode_huffman(
    data: bytes,
    add_parity: bool = False,
    k_value: int = 7,
    parity_rule: str = PARITY_RULE_GC_EVEN_A_ODD_T
) -> Tuple[str, Dict[int, str], int]:
    """Encodes a byte string using Huffman coding and maps to a DNA sequence.

    Optionally, parity nucleotides can be added to the DNA sequence for error
    detection using the specified rule and k-value.

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
          - "01" -> 'C'
          - "10" -> 'G'
          - "11" -> 'T'
    7.  If `add_parity` is True, the generated DNA sequence is further processed
        to include parity bits.

    Args:
        data (bytes): The byte string to encode.
        add_parity (bool): If True, add parity nucleotides to the encoded DNA
                           sequence. Defaults to False.
        k_value (int): The size of each data block for parity calculation if
                       `add_parity` is True. Defaults to 7. Must be positive.
        parity_rule (str): The parity rule to use if `add_parity` is True.
                           Defaults to `PARITY_RULE_GC_EVEN_A_ODD_T`.

    Returns:
        Tuple[str, Dict[int, str], int]: A tuple containing:
            - dna_sequence (str): The final DNA sequence, possibly with parity
                                  nucleotides interleaved.
            - huffman_table (Dict[int, str]): The Huffman table used for encoding.
            - num_padding_bits (int): Number of '0's added to the binary string
                                      before DNA mapping.
    
    Raises:
        ValueError: If `add_parity` is True and `k_value` is not positive.
        NotImplementedError: If `add_parity` is True and `parity_rule` is unknown.
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
    # Map every pair of bits to a nucleotide using the shared mapping.
    dna_mapping = DNA_ENCODE_MAP

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

    if add_parity:
        if k_value <= 0:
            raise ValueError("k_value must be positive for parity addition.")
        dna_sequence = add_parity_to_sequence(dna_sequence, k_value, parity_rule)

    return dna_sequence, huffman_table, num_padding_bits


# --- Main Decoding Function ---

def decode_huffman(
    dna_sequence: str, 
    huffman_table: Dict[int, str], 
    num_padding_bits: int,
    check_parity: bool = False,
    k_value: int = 7,
    parity_rule: str = PARITY_RULE_GC_EVEN_A_ODD_T
) -> Tuple[bytes, List[int]]:
    """Decodes a Huffman-encoded DNA sequence back into the original byte string.

    Optionally, this function can check for parity errors if the sequence was
    encoded with parity bits.

    The process involves:
    1.  Converting the DNA sequence back into its binary string representation
        using the mapping: 'A' -> "00", 'C' -> "01", 'G' -> "10", 'T' -> "11".
    2.  Removing any padding bits from the end of the binary string, based on 
        `num_padding_bits`.
    3.  Inverting the provided `huffman_table` to map binary codes back to 
        original byte values.
    4.  Iterating through the unpadded binary string, matching prefixes against 
        the inverted Huffman codes to reconstruct the original bytes.

    Args:
        dna_sequence (str): The DNA sequence string to decode, possibly
                            including parity bits.
        huffman_table (Dict[int, str]): The Huffman table used for encoding.
        num_padding_bits (int): The number of '0's added to the binary string
                                before DNA mapping during encoding.
        check_parity (bool): If True, verify parity and report errors.
                             Defaults to False.
        k_value (int): The size of data blocks used during parity encoding if
                       `check_parity` is True. Defaults to 7. Must be positive.
        parity_rule (str): The parity rule used if `check_parity` is True.
                           Defaults to `PARITY_RULE_GC_EVEN_A_ODD_T`.

    Returns:
        Tuple[bytes, List[int]]: A tuple containing:
            - bytes: The decoded byte string.
            - List[int]: A list of 0-based indices of data blocks where parity
                         errors were detected. Empty if `check_parity` is False
                         or no errors were found.

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
    parity_errors: List[int] = []
    sequence_for_huffman_decode = dna_sequence

    if check_parity:
        if k_value <= 0:
            raise ValueError("k_value must be positive for parity checking.")
        # strip_and_verify_parity may raise ValueError or NotImplementedError
        sequence_for_huffman_decode, parity_errors = strip_and_verify_parity(
            dna_sequence, k_value, parity_rule
        )

    # Handle consistent empty input: empty sequence, empty table, zero padding.
    # This check should use sequence_for_huffman_decode if parity was stripped.
    if not sequence_for_huffman_decode and not huffman_table and num_padding_bits == 0:
        # If parity checking resulted in an empty sequence, and other params match empty,
        # it's a valid empty decode. Parity errors list will be returned as is.
        return b"", parity_errors


    # 1. Convert DNA sequence (potentially stripped of parity) to its binary string.
    binary_digits_list: List[str] = []
    for char_dna in sequence_for_huffman_decode:  # Use the (potentially) stripped sequence
        binary_pair = DNA_DECODE_MAP.get(char_dna)
        if binary_pair is None:
            raise ValueError(
                f"Invalid DNA character '{char_dna}' in sequence for Huffman decoding."
            )
        binary_digits_list.append(binary_pair)
    encoded_binary_string = "".join(binary_digits_list)

    # Handle if DNA conversion results in an empty binary string.
    if not encoded_binary_string:
        if not huffman_table and num_padding_bits == 0: 
            return b"", parity_errors # Return parity_errors as well
        raise ValueError(
            "Empty binary string derived from (potentially parity-stripped) DNA, "
            "but Huffman table or padding suggests data was expected."
        )

    # 2. Remove Huffman padding bits. ``num_padding_bits`` tells us how many
    # trailing '0's were added solely to satisfy the 2-bit DNA packing.  These
    # bits carry no information and must be stripped before decoding the Huffman
    # codes.
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
        if not huffman_table:
            return b"", parity_errors  # Return parity_errors
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
    # ``current_code_buffer`` accumulates bits until they match a Huffman code
    # from ``inverted_huffman_table``.  Using a list for the buffer avoids the
    # overhead of repeatedly concatenating Python strings.
    current_code_buffer = []
    for bit in unpadded_binary_string:
        current_code_buffer.append(bit)
        current_prefix = "".join(current_code_buffer)
        if current_prefix in inverted_huffman_table:
            byte_val = inverted_huffman_table[current_prefix]
            decoded_bytes_list.append(bytes([byte_val]))
            current_code_buffer = [] # Reset buffer
    
    # If there are remaining bits in ``current_code_buffer`` after processing
    # the entire bit string, it means the last bits did not match any Huffman
    # code.  This typically indicates data corruption or that an incorrect table
    # was supplied.
    if current_code_buffer:
        raise ValueError(
            "Corrupted data or incorrect Huffman table: "
            f"remaining unparsed bits '{''.join(current_code_buffer)}'."
        )

    return b"".join(decoded_bytes_list), parity_errors
