import argparse
import sys # For potential sys.path modification or exit
from genecoder.encoders import encode_base4_direct, decode_base4_direct
from genecoder.formats import to_fasta # Import the FASTA formatter

def main():
    """Main function to handle CLI argument parsing and command execution."""
    parser = argparse.ArgumentParser(description="GeneCoder: Encode and decode data into simulated DNA sequences.")
    subparsers = parser.add_subparsers(dest='command', help='Available commands', required=True)

    # Encode command parser
    encode_parser = subparsers.add_parser('encode', help='Encode data into a DNA sequence.')
    encode_parser.add_argument('--input-file', type=str, required=True, help='Path to the input file to encode.')
    encode_parser.add_argument('--output-file', type=str, required=True, help='Path to save the encoded DNA sequence.')
    encode_parser.add_argument('--method', type=str, default='base4_direct', choices=['base4_direct'], help='Encoding method to use (default: base4_direct).')

    # Decode command parser
    decode_parser = subparsers.add_parser('decode', help='Decode a DNA sequence back to data.')
    decode_parser.add_argument('--input-file', type=str, required=True, help='Path to the input DNA file to decode.')
    decode_parser.add_argument('--output-file', type=str, required=True, help='Path to save the decoded data.')
    decode_parser.add_argument('--method', type=str, default='base4_direct', choices=['base4_direct'], help='Decoding method to use (default: base4_direct).')

    args = parser.parse_args()

    if args.command == 'encode':
        if args.method == 'base4_direct':
            try:
                with open(args.input_file, 'rb') as f_in:
                    input_data = f_in.read()
                
                encoded_dna = encode_base4_direct(input_data)
                
                # Create FASTA header
                fasta_header = f"method={args.method} input_file={args.input_file}"
                
                # Format the DNA sequence as FASTA
                fasta_output = to_fasta(encoded_dna, fasta_header, line_width=80) # Using line_width=80
                
                with open(args.output_file, 'w', encoding='utf-8') as f_out:
                    f_out.write(fasta_output)
                
                print(f"Successfully encoded '{args.input_file}' to '{args.output_file}' in FASTA format using '{args.method}' method.")

            except FileNotFoundError:
                print(f"Error: Input file '{args.input_file}' not found.")
                sys.exit(1)
            except IOError as e:
                print(f"Error during file operation: {e}")
                sys.exit(1)
            except ValueError as e: # Catch potential errors from to_fasta (e.g. invalid line_width)
                print(f"Error during FASTA formatting: {e}")
                sys.exit(1)
            except Exception as e:
                print(f"An unexpected error occurred during encoding: {e}")
                sys.exit(1)
        else:
            print(f"Error: Encoding method '{args.method}' is not supported.")
            sys.exit(1)

    elif args.command == 'decode':
        if args.method == 'base4_direct':
            try:
                with open(args.input_file, 'r', encoding='utf-8') as f_in:
                    dna_sequence = f_in.read().strip() # Read and strip trailing newlines
                
                decoded_data = decode_base4_direct(dna_sequence)
                
                with open(args.output_file, 'wb') as f_out:
                    f_out.write(decoded_data)
                
                print(f"Successfully decoded '{args.input_file}' to '{args.output_file}' using '{args.method}' method.")

            except FileNotFoundError:
                print(f"Error: Input file '{args.input_file}' not found.")
                sys.exit(1)
            except IOError as e:
                print(f"Error during file operation: {e}")
                sys.exit(1)
            except ValueError as e: # Catch errors from decoder (e.g., invalid DNA)
                print(f"Error during decoding: {e}")
                sys.exit(1)
            except Exception as e:
                print(f"An unexpected error occurred during decoding: {e}")
                sys.exit(1)
        else:
            print(f"Error: Decoding method '{args.method}' is not supported.")
            sys.exit(1)

if __name__ == '__main__':
    main()
