"""Command-Line Interface (CLI) for GeneCoder.

This module provides the main entry point for users to interact with GeneCoder
to encode data into simulated DNA sequences and decode them back. It uses
`argparse` to handle command-line arguments for different operations like
encoding and decoding, supporting various methods such as Base-4 Direct Mapping
and Huffman coding.
"""
import argparse
import sys 
import json 
from genecoder.encoders import encode_base4_direct, decode_base4_direct
from genecoder.formats import to_fasta, from_fasta
from genecoder.huffman_coding import encode_huffman, decode_huffman
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T # Import parity constant

def main() -> None:
    """Parses command-line arguments and executes the requested GeneCoder command.

    This function sets up the argument parser for `encode` and `decode` commands,
    each with options for input/output files and encoding/decoding methods.
    It then calls the appropriate functions based on the parsed arguments to
    perform file I/O, encoding/decoding, FASTA formatting, and metric display.

    Side effects:
        Prints information, progress, metrics, or error messages to stdout/stderr.
        Reads from input files and writes to output files.
        Calls `sys.exit(1)` on critical errors.
    """
    parser = argparse.ArgumentParser(
        description="GeneCoder: Encode and decode data into simulated DNA sequences."
    )
    subparsers = parser.add_subparsers(
        dest='command', 
        help='Available commands. Use `<command> -h` for more details.', 
        required=True
    )

    # Encode command parser
    encode_parser = subparsers.add_parser('encode', help='Encode data into a DNA sequence.')
    encode_parser.add_argument('--input-file', type=str, required=True, help='Path to the input file to encode.')
    encode_parser.add_argument('--output-file', type=str, required=True, help='Path to save the encoded DNA sequence.')
    encode_parser.add_argument(
        '--method', 
        type=str, 
        default='base4_direct', 
        choices=['base4_direct', 'huffman'], 
        help='Encoding method to use (default: base4_direct).'
    )
    # Parity arguments for encode
    encode_parser.add_argument(
        '--add-parity',
        action='store_true',
        help='Add parity bits to the encoded sequence (applies to base4_direct and huffman).'
    )
    encode_parser.add_argument(
        '--k-value',
        type=int,
        default=7,
        help='Size of data blocks for parity calculation (default: 7).'
    )
    encode_parser.add_argument(
        '--parity-rule',
        type=str,
        default=PARITY_RULE_GC_EVEN_A_ODD_T,
        choices=[PARITY_RULE_GC_EVEN_A_ODD_T], # Add more rules here in future
        help='Parity rule to use (default: GC_even_A_odd_T).'
    )

    # Decode command parser
    decode_parser = subparsers.add_parser('decode', help='Decode a DNA sequence back to data.')
    decode_parser.add_argument(
        '--input-file', 
        type=str, 
        required=True, 
        help='Path to the input DNA file to decode (FASTA format expected for Huffman).'
    )
    decode_parser.add_argument(
        '--output-file', 
        type=str, 
        required=True, 
        help='Path to save the decoded data.'
    )
    decode_parser.add_argument(
        '--method', 
        type=str, 
        default='base4_direct', 
        choices=['base4_direct', 'huffman'], 
        help='Decoding method to use (default: base4_direct).'
    )
    # Parity arguments for decode
    decode_parser.add_argument(
        '--check-parity',
        action='store_true',
        help='Check parity bits during decoding (applies to base4_direct and huffman).'
    )
    decode_parser.add_argument(
        '--k-value',
        type=int,
        default=7,
        help='Size of data blocks for parity checking (default: 7).'
    )
    decode_parser.add_argument(
        '--parity-rule',
        type=str,
        default=PARITY_RULE_GC_EVEN_A_ODD_T,
        choices=[PARITY_RULE_GC_EVEN_A_ODD_T], # Add more rules here in future
        help='Parity rule used during encoding (default: GC_even_A_odd_T).'
    )

    args = parser.parse_args()

    if args.command == 'encode':
        try:
            with open(args.input_file, 'rb') as f_in:
                input_data = f_in.read()

            if args.method == 'base4_direct':
                if args.add_parity and args.k_value <= 0:
                    print("Error: --k-value must be positive when adding parity.")
                    sys.exit(1)
                encoded_dna_sequence = encode_base4_direct(
                    input_data, 
                    add_parity=args.add_parity, 
                    k_value=args.k_value, 
                    parity_rule=args.parity_rule
                )
                fasta_header_parts = [
                    f"method={args.method}",
                    f"input_file={args.input_file}"
                ]
                if args.add_parity:
                    fasta_header_parts.append(f"parity_k={args.k_value}")
                    fasta_header_parts.append(f"parity_rule={args.parity_rule}")
                fasta_header = " ".join(fasta_header_parts)
                fasta_output = to_fasta(encoded_dna_sequence, fasta_header, line_width=80)
            
            elif args.method == 'huffman':
                if args.add_parity and args.k_value <= 0:
                    print("Error: --k-value must be positive when adding parity for Huffman.")
                    sys.exit(1)
                encoded_dna_sequence, huffman_table, num_padding_bits = encode_huffman(
                    input_data,
                    add_parity=args.add_parity,
                    k_value=args.k_value,
                    parity_rule=args.parity_rule
                )
                # Serialize Huffman table (keys to str) and padding bits for FASTA header
                serializable_huffman_table = {str(k): v for k, v in huffman_table.items()}
                huffman_params = {
                    "table": serializable_huffman_table, 
                    "padding": num_padding_bits
                    # Parity info for Huffman is implicitly part of the DNA sequence if added,
                    # and rule/k-value are passed during decode.
                    # We could also add explicit parity_k and parity_rule to huffman_params if desired
                    # for more self-documenting FASTA, but it's not strictly needed for decoding
                    # if CLI provides them. For now, CLI drives parity for Huffman decode.
                }
                huffman_params_json = json.dumps(huffman_params)
                
                fasta_header_parts = [
                    f"method=huffman",
                    f"input_file={args.input_file}",
                    f"huffman_params={huffman_params_json}"
                ]
                if args.add_parity: # Add parity info to header if used with Huffman
                    fasta_header_parts.append(f"parity_k={args.k_value}")
                    fasta_header_parts.append(f"parity_rule={args.parity_rule}")
                fasta_header = " ".join(fasta_header_parts)

                fasta_output = to_fasta(encoded_dna_sequence, fasta_header, line_width=80)
            
            else: # Should not happen due to argparse choices
                # This case is theoretically unreachable due to `argparse` choices constraint.
                print(f"Error: Encoding method '{args.method}' is not supported.")
                sys.exit(1)

            with open(args.output_file, 'w', encoding='utf-8') as f_out:
                f_out.write(fasta_output)

            # Calculate and Print Metrics
            original_size_bytes = len(input_data)
            encoded_dna_length_nucleotides = len(encoded_dna_sequence)

            compression_ratio_denom = encoded_dna_length_nucleotides * 0.25 # Each nt is 2 bits = 0.25 bytes
            if original_size_bytes == 0 and compression_ratio_denom == 0:
                 compression_ratio = 0.0 # Or 1.0 if preferred for empty to empty
            elif compression_ratio_denom == 0:
                compression_ratio = float('inf') if original_size_bytes > 0 else 0.0
            else:
                compression_ratio = original_size_bytes / compression_ratio_denom
            
            bits_per_nucleotide = (original_size_bytes * 8) / encoded_dna_length_nucleotides if encoded_dna_length_nucleotides != 0 else 0.0

            print("\n--- Encoding Metrics ---")
            print(f"Original file size: {original_size_bytes} bytes")
            print(f"Encoded DNA length: {encoded_dna_length_nucleotides} nucleotides")
            print(f"Compression ratio: {compression_ratio:.2f} (original bytes / DNA bytes equivalent)")
            print(f"Bits per nucleotide: {bits_per_nucleotide:.2f} bits/nt")
            print("----------------------\n")
            
            print(f"Successfully encoded '{args.input_file}' to '{args.output_file}' in FASTA format using '{args.method}' method.")

        except FileNotFoundError:
            print(f"Error: Input file '{args.input_file}' not found.")
            sys.exit(1)
        except IOError as e:
            print(f"Error during file operation: {e}")
            sys.exit(1)
        except (ValueError, json.JSONDecodeError) as e: 
            print(f"Error during encoding or FASTA formatting/JSON processing: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"An unexpected error occurred during encoding: {e}")
            sys.exit(1)

    elif args.command == 'decode':
        try:
            with open(args.input_file, 'r', encoding='utf-8') as f_in:
                file_content_str = f_in.read()

            parsed_records = from_fasta(file_content_str)

            if not parsed_records:
                print(f"Error: No valid FASTA records found in '{args.input_file}'.")
                sys.exit(1)
            
            if len(parsed_records) > 1:
                print(f"Warning: Multiple FASTA records found in '{args.input_file}'. Processing the first one only.")

            header, dna_sequence = parsed_records[0] # Process only the first record

            if args.method == 'base4_direct':
                if args.check_parity and args.k_value <= 0:
                    print("Error: --k-value must be positive when checking parity.")
                    sys.exit(1)
                
                # The `dna_sequence` from `from_fasta` is already a single string of sequence characters.
                # Parity parameters are taken from CLI args for base4_direct.
                # Header for base4_direct might contain parity info, but we use CLI args to decide if/how to check.
                decoded_data, parity_errors = decode_base4_direct(
                    dna_sequence,
                    check_parity=args.check_parity,
                    k_value=args.k_value,
                    parity_rule=args.parity_rule
                )
                if args.check_parity and parity_errors:
                    print(f"Warning: Parity errors detected in the following 0-based data blocks: {parity_errors}")
            
            elif args.method == 'huffman':
                if args.check_parity and args.k_value <= 0:
                    print("Error: --k-value must be positive when checking parity for Huffman.")
                    sys.exit(1)
                
                # For Huffman, extract parameters (Huffman table, padding) from the FASTA header.
                # Parity parameters (k_value, rule) are taken from CLI args for Huffman.
                try:
                    # Attempt to find the 'huffman_params={...}' field in the header.
                    # This parsing is basic and assumes the JSON string is the last part of 
                    # the 'huffman_params=' field. More complex headers might require regex.
                    json_param_field_start = header.find("huffman_params=")
                    if json_param_field_start == -1:
                        raise ValueError(
                            "FASTA header for Huffman method does not contain "
                            "'huffman_params=' field."
                        )
                    
                    # Extract the substring starting from "huffman_params="
                    json_part_with_key = header[json_param_field_start + len("huffman_params="):]

                    # Locate the start and end of the JSON object ({...})
                    first_bracket_index = json_part_with_key.find('{')
                    if first_bracket_index == -1:
                        raise ValueError(
                            "Could not find start of JSON object for huffman_params in header."
                        )
                    
                    open_brackets = 0
                    json_end_index = -1
                    for i, char in enumerate(json_part_with_key[first_bracket_index:]):
                        if char == '{':
                            open_brackets += 1
                        elif char == '}':
                            open_brackets -= 1
                            if open_brackets == 0:
                                json_end_index = first_bracket_index + i + 1
                                break
                    
                    if json_end_index == -1 :
                        raise ValueError(
                            "Could not find end of JSON object for huffman_params in header."
                        )

                    params_json_str = json_part_with_key[first_bracket_index:json_end_index]
                    
                    huffman_params = json.loads(params_json_str)
                    
                    # Retrieve table and padding, ensuring they exist.
                    huffman_table_str_keys = huffman_params.get('table')
                    num_padding_bits = huffman_params.get('padding')

                    if huffman_table_str_keys is None or num_padding_bits is None:
                        raise ValueError(
                            "Huffman parameters 'table' or 'padding' missing in "
                            "FASTA header JSON."
                        )
                    
                    # Convert Huffman table keys back to integers.
                    huffman_table = {
                        int(k): v for k, v in huffman_table_str_keys.items()
                    }
                    
                except (ValueError, json.JSONDecodeError, KeyError, TypeError) as e:
                    # Catch specific errors from parsing logic, json.loads, or dict access.
                    print(f"Error parsing Huffman parameters from FASTA header: {e}")
                    sys.exit(1)
                
                
                decoded_data, parity_errors = decode_huffman(
                    dna_sequence, 
                    huffman_table, 
                    num_padding_bits,
                    check_parity=args.check_parity,
                    k_value=args.k_value,
                    parity_rule=args.parity_rule
                )
                if args.check_parity and parity_errors:
                    print(f"Warning: Parity errors detected in the following 0-based data blocks: {parity_errors}")
            
            else: # Should not happen due to argparse choices
                # This case is theoretically unreachable.
                print(f"Error: Decoding method '{args.method}' is not supported.")
                sys.exit(1)

            with open(args.output_file, 'wb') as f_out:
                f_out.write(decoded_data)
            
            print(f"Successfully decoded '{args.input_file}' to '{args.output_file}' using '{args.method}' method.")
            
        except FileNotFoundError:
            print(f"Error: Input file '{args.input_file}' not found.")
            sys.exit(1)
        except IOError as e:
            print(f"Error during file operation: {e}")
            sys.exit(1)
        except (ValueError, json.JSONDecodeError) as e: # Catch errors from decoder, JSON, or header parsing
            print(f"Error during decoding: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"An unexpected error occurred during decoding: {e}")
            sys.exit(1)

if __name__ == '__main__':
    main()
