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
import os
import random
import re  # For parsing header parameters
import concurrent.futures
from genecoder.encoders import (
    encode_base4_direct,
    decode_base4_direct,
    encode_gc_balanced,
    decode_gc_balanced,
    calculate_gc_content,
    get_max_homopolymer_length,
)
from genecoder.encoders import (
    encode_triple_repeat,
    decode_triple_repeat,
)  # DNA-level FEC
from genecoder.hamming_codec import (
    encode_data_with_hamming,
    decode_data_with_hamming,
)  # Binary-level FEC
from genecoder.formats import to_fasta, from_fasta
from genecoder.huffman_coding import encode_huffman, decode_huffman
from genecoder.error_detection import (
    PARITY_RULE_GC_EVEN_A_ODD_T,
)  # Import parity constant
from genecoder.error_simulation import introduce_errors
from genecoder.plotting import (
    calculate_windowed_gc_content,
    identify_homopolymer_regions,
    generate_sequence_analysis_plot,
)


# --- Helper function for single file encoding ---
def process_single_encode(
    input_file_path: str, output_file_path: str, args: argparse.Namespace
) -> None:
    """Encodes a single file based on provided arguments."""
    print(
        f"\nProcessing encode for input: {input_file_path} -> output: {output_file_path}"
    )
    try:
        with open(input_file_path, "rb") as f_in:
            original_input_data = f_in.read()  # Store original for metrics

        current_input_data = original_input_data
        fec_padding_bits = -1  # Placeholder, only relevant for Hamming

        fasta_header_parts = [
            f"method={args.method}",
            f"input_file={os.path.basename(input_file_path)}",
        ]

        # Apply Hamming FEC *before* DNA encoding if specified
        if args.fec == "hamming_7_4":
            if args.add_parity:
                print(
                    f"Warning for {input_file_path}: --add-parity is ignored when Hamming(7,4) FEC is applied to binary data.",
                    file=sys.stderr,
                )
            current_input_data, fec_padding_bits = encode_data_with_hamming(
                original_input_data
            )
            fasta_header_parts.append("fec=hamming_7_4")
            fasta_header_parts.append(f"fec_padding_bits={fec_padding_bits}")
            print(
                f"Applied Hamming(7,4) FEC to {input_file_path}. Original binary size: {len(original_input_data)}, Hamming encoded binary size: {len(current_input_data)} (padding bits: {fec_padding_bits})."
            )

        # DNA Encoding methods
        raw_encoded_dna = ""
        # Determine if parity should be applied (only if Hamming not used)
        should_add_parity = args.add_parity and args.fec != "hamming_7_4"

        if args.method == "base4_direct":
            if should_add_parity and args.k_value <= 0:
                print(
                    f"Error for {input_file_path}: Parity k-value must be positive.",
                    file=sys.stderr,
                )
                return
            raw_encoded_dna = encode_base4_direct(
                current_input_data,
                add_parity=should_add_parity,
                k_value=args.k_value,
                parity_rule=args.parity_rule,
            )
            if should_add_parity:
                fasta_header_parts.extend(
                    [f"parity_k={args.k_value}", f"parity_rule={args.parity_rule}"]
                )

        elif args.method == "huffman":
            if should_add_parity and args.k_value <= 0:
                print(
                    f"Error for {input_file_path}: Parity k-value must be positive for Huffman.",
                    file=sys.stderr,
                )
                return
            raw_encoded_dna, huffman_table, num_padding_bits = encode_huffman(
                current_input_data,
                add_parity=should_add_parity,
                k_value=args.k_value,
                parity_rule=args.parity_rule,
            )
            serializable_table = {str(k): v for k, v in huffman_table.items()}
            huffman_params = {"table": serializable_table, "padding": num_padding_bits}
            fasta_header_parts.append(f"huffman_params={json.dumps(huffman_params)}")
            if should_add_parity:
                fasta_header_parts.extend(
                    [f"parity_k={args.k_value}", f"parity_rule={args.parity_rule}"]
                )

        elif args.method == "gc_balanced":
            target_gc_min = args.gc_min
            target_gc_max = args.gc_max
            max_homopolymer_constraint = args.max_homopolymer
            if should_add_parity:  # Parity is not part of gc_balanced's core logic
                print(
                    f"Warning for {input_file_path}: --add-parity not directly used by 'gc_balanced' core logic.",
                    file=sys.stderr,
                )
            raw_encoded_dna = encode_gc_balanced(
                current_input_data,
                target_gc_min,
                target_gc_max,
                max_homopolymer_constraint,
            )
            fasta_header_parts.extend(
                [
                    f"gc_min={target_gc_min}",
                    f"gc_max={target_gc_max}",
                    f"max_homopolymer={max_homopolymer_constraint}",
                ]
            )

        else:
            print(
                f"Error for {input_file_path}: Unknown encoding method '{args.method}'.",
                file=sys.stderr,
            )
            return

        # Apply Triple-Repeat FEC *after* DNA encoding if specified
        final_encoded_dna_sequence = raw_encoded_dna
        if args.fec == "triple_repeat":
            if (
                args.fec == "hamming_7_4"
            ):  # This case should not be hit if logic is correct above, but as safeguard
                print(
                    f"Error for {input_file_path}: Cannot apply both hamming_7_4 and triple_repeat FEC.",
                    file=sys.stderr,
                )  # Should be handled by arg choices
                return  # Or handle as priority, e.g. Hamming first
            final_encoded_dna_sequence = encode_triple_repeat(raw_encoded_dna)
            fasta_header_parts.append(
                "fec=triple_repeat"
            )  # Ensure this is not duplicated if Hamming was also added
            print(
                f"Applied Triple-Repeat FEC to {input_file_path}. DNA length before: {len(raw_encoded_dna)}, after: {len(final_encoded_dna_sequence)}."
            )
        elif (
            args.fec is not None and args.fec != "hamming_7_4"
        ):  # Unknown FEC if not already handled
            print(
                f"Warning for {input_file_path}: Unknown FEC method '{args.fec}'. No DNA-level FEC applied.",
                file=sys.stderr,
            )

        fasta_header = " ".join(fasta_header_parts)
        fasta_output = to_fasta(final_encoded_dna_sequence, fasta_header, line_width=80)

        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
        with open(output_file_path, "w", encoding="utf-8") as f_out:
            f_out.write(fasta_output)

        # Metrics based on original_input_data and final_encoded_dna_sequence
        original_size_bytes = len(original_input_data)
        final_encoded_length_nucleotides = len(final_encoded_dna_sequence)
        dna_equivalent_bytes = final_encoded_length_nucleotides * 0.25

        compression_ratio = (
            original_size_bytes / dna_equivalent_bytes
            if dna_equivalent_bytes > 0
            else (float("inf") if original_size_bytes > 0 else 0.0)
        )
        bits_per_nucleotide = (
            (original_size_bytes * 8) / final_encoded_length_nucleotides
            if final_encoded_length_nucleotides != 0
            else 0.0
        )

        print(f"\n--- Encoding Metrics for {input_file_path} ---")
        print(f"Original file size: {original_size_bytes} bytes")
        if args.fec == "hamming_7_4":
            print(
                f"Binary size after Hamming(7,4) FEC: {len(current_input_data)} bytes (padding: {fec_padding_bits} bits)"
            )
        print(
            f"Final Encoded DNA length: {final_encoded_length_nucleotides} nucleotides (after any DNA-level FEC like triple_repeat)"
        )
        print(
            f"Compression ratio: {compression_ratio:.2f} (original bytes / final DNA bytes equivalent)"
        )
        print(
            f"Bits per nucleotide: {bits_per_nucleotide:.2f} bits/nt (based on original data and final DNA length)"
        )

        if args.method == "gc_balanced":
            # GC content and homopolymer for gc_balanced are reported on the sequence *before* DNA-level FEC
            # but *after* the gc_balanced signal bit is added. This raw_encoded_dna is from the (potentially Hamming-coded) current_input_data.
            gc_balanced_payload_dna = (
                raw_encoded_dna[1:] if len(raw_encoded_dna) > 0 else ""
            )
            print(
                f"Actual GC content (gc_balanced payload, pre-DNA FEC): {calculate_gc_content(gc_balanced_payload_dna):.2%}"
            )
            print(
                f"Actual max homopolymer length (gc_balanced payload, pre-DNA FEC): {get_max_homopolymer_length(gc_balanced_payload_dna)}"
            )
        print("----------------------")
        print(f"Successfully encoded '{input_file_path}' to '{output_file_path}'.")

    except FileNotFoundError:
        print(f"Error for {input_file_path}: Input file not found.", file=sys.stderr)
    except IOError as e:
        print(f"Error for {input_file_path}: I/O error: {e}", file=sys.stderr)
    except Exception as e:
        print(
            f"Error for {input_file_path}: Unexpected error during encoding: {e}",
            file=sys.stderr,
        )


# --- Helper function for single file decoding ---
def process_single_decode(
    input_file_path: str, output_file_path: str, args: argparse.Namespace
) -> None:
    """Decodes a single file based on provided arguments."""
    print(
        f"\nProcessing decode for input: {input_file_path} -> output: {output_file_path}"
    )
    try:
        with open(input_file_path, "r", encoding="utf-8") as f_in:
            file_content_str = f_in.read()

        parsed_records = from_fasta(file_content_str)
        if not parsed_records:
            print(
                f"Error for {input_file_path}: No valid FASTA records found.",
                file=sys.stderr,
            )
            return

        if len(parsed_records) > 1:
            print(
                f"Warning for {input_file_path}: Multiple FASTA records found. Processing the first one only.",
                file=sys.stderr,
            )

        header, sequence_from_fasta = parsed_records[0]

        header_method_match = re.search(r"method=([\w_]+)", header)
        if header_method_match:
            header_method = header_method_match.group(1)
            if header_method != args.method:
                print(
                    f"Error for {input_file_path}: FASTA header specifies method '{header_method}', but --method '{args.method}' was provided. Aborting.",
                    file=sys.stderr,
                )
                sys.exit(1)

        # --- DNA-level FEC decoding (Triple Repeat) ---
        dna_sequence_for_primary_decode = sequence_from_fasta
        if "fec=triple_repeat" in header:
            print(f"Triple-Repeat FEC detected in header for {input_file_path}.")
            if len(sequence_from_fasta) % 3 != 0:
                print(
                    f"Warning for {input_file_path}: Sequence length {len(sequence_from_fasta)} is not multiple of 3 for Triple-Repeat FEC. Attempting decode, but it might fail or be incorrect.",
                    file=sys.stderr,
                )
            try:
                dna_sequence_for_primary_decode, corrected_tr, uncorr_tr = (
                    decode_triple_repeat(sequence_from_fasta)
                )
                print(
                    f"Triple-Repeat FEC decoding for {input_file_path}: {corrected_tr} corrected, {uncorr_tr} uncorrectable errors in triplets."
                )
            except (
                ValueError
            ) as ve:  # Catch error if decode_triple_repeat itself raises it
                print(
                    f"Error during Triple-Repeat FEC decoding for {input_file_path}: {ve}. Using sequence as is for primary decode.",
                    file=sys.stderr,
                )
                # dna_sequence_for_primary_decode remains sequence_from_fasta

        # --- Primary DNA Decoding (to intermediate binary) ---
        intermediate_binary_data = b""
        parity_errors = []  # For DNA-level parity, not Hamming

        # Determine if DNA-level parity should be checked (only if Hamming not primary FEC)
        should_check_dna_parity = args.check_parity and "fec=hamming_7_4" not in header

        if args.method == "base4_direct":
            if should_check_dna_parity and args.k_value <= 0:
                print(
                    f"Error for {input_file_path}: Parity k-value must be positive for DNA-level parity.",
                    file=sys.stderr,
                )
                return
            intermediate_binary_data, parity_errors = decode_base4_direct(
                dna_sequence_for_primary_decode,
                check_parity=should_check_dna_parity,
                k_value=args.k_value,
                parity_rule=args.parity_rule,
            )
        elif args.method == "huffman":
            if should_check_dna_parity and args.k_value <= 0:
                print(
                    f"Error for {input_file_path}: Parity k-value must be positive for Huffman DNA-level parity.",
                    file=sys.stderr,
                )
                return
            try:  # Parsing Huffman params from header
                json_param_field_start = header.find("huffman_params=")
                if json_param_field_start == -1:
                    raise ValueError("Huffman params field missing.")
                json_part_with_key = header[
                    json_param_field_start + len("huffman_params=") :
                ]
                first_bracket = json_part_with_key.find("{")
                if first_bracket == -1:
                    raise ValueError("Huffman JSON object start missing.")
                open_br = 0
                json_end = -1
                for i, char_h in enumerate(json_part_with_key[first_bracket:]):
                    if char_h == "{":
                        open_br += 1
                    elif char_h == "}":
                        open_br -= 1
                    if open_br == 0:
                        json_end = first_bracket + i + 1
                        break
                if json_end == -1:
                    raise ValueError("Huffman JSON object end missing.")
                params_json_str = json_part_with_key[first_bracket:json_end]
                huffman_params = json.loads(params_json_str)
                huffman_table = {int(k): v for k, v in huffman_params["table"].items()}
                num_padding_bits = huffman_params["padding"]
                if huffman_table is None or num_padding_bits is None:
                    raise ValueError("Huffman table/padding missing.")

                intermediate_binary_data, parity_errors = decode_huffman(
                    dna_sequence_for_primary_decode,
                    huffman_table,
                    num_padding_bits,
                    check_parity=should_check_dna_parity,
                    k_value=args.k_value,
                    parity_rule=args.parity_rule,
                )
            except Exception as e:
                print(
                    f"Error for {input_file_path}: Invalid Huffman params in header: {e}",
                    file=sys.stderr,
                )
                return
        elif args.method == "gc_balanced":
            if should_check_dna_parity:
                # gc_balanced does not use this type of parity
                print(
                    f"Warning for {input_file_path}: --check-parity is not applicable to 'gc_balanced' method's DNA layer.",
                    file=sys.stderr,
                )
            try:  # Parsing GC-Balanced params from header
                gc_min_match = re.search(r"gc_min=([\d.]+)", header)
                gc_max_match = re.search(r"gc_max=([\d.]+)", header)
                max_hp_match = re.search(r"max_homopolymer=(\d+)", header)
                gc_min = float(gc_min_match.group(1)) if gc_min_match else None
                gc_max = float(gc_max_match.group(1)) if gc_max_match else None
                max_hp = int(max_hp_match.group(1)) if max_hp_match else None
                if not all([gc_min, gc_max, max_hp]):
                    print(
                        f"Warning for {input_file_path}: Could not parse all GC constraint params from header for gc_balanced.",
                        file=sys.stderr,
                    )
                intermediate_binary_data = decode_gc_balanced(
                    dna_sequence_for_primary_decode,
                    expected_gc_min=gc_min,
                    expected_gc_max=gc_max,
                    expected_max_homopolymer=max_hp,
                )
            except Exception as e:
                print(
                    f"Error for {input_file_path}: GC-balanced decoding/param parsing: {e}",
                    file=sys.stderr,
                )
                return
        else:
            print(
                f"Error for {input_file_path}: Unknown decoding method '{args.method}'.",
                file=sys.stderr,
            )
            return

        if should_check_dna_parity and parity_errors:
            print(
                f"Warning for {input_file_path}: DNA-level parity errors in data blocks: {parity_errors}",
                file=sys.stderr,
            )

        # --- Binary-level FEC decoding (Hamming) ---
        final_decoded_data = intermediate_binary_data
        if "fec=hamming_7_4" in header:
            print(f"Hamming(7,4) FEC detected in header for {input_file_path}.")
            fec_padding_bits_match = re.search(r"fec_padding_bits=(\d+)", header)
            if not fec_padding_bits_match:
                print(
                    f"Error for {input_file_path}: 'fec_padding_bits' missing in header for Hamming(7,4) FEC. Cannot decode.",
                    file=sys.stderr,
                )
                return  # Critical error, cannot proceed with Hamming decode

            fec_padding_bits = int(fec_padding_bits_match.group(1))
            try:
                final_decoded_data, corrected_ham = decode_data_with_hamming(
                    intermediate_binary_data, fec_padding_bits
                )
                print(
                    f"Hamming(7,4) FEC decoding for {input_file_path}: {corrected_ham} corrected errors in codewords."
                )
            except (
                ValueError
            ) as ve:  # Catch errors from decode_data_with_hamming (e.g. invalid length)
                print(
                    f"Error during Hamming(7,4) FEC decoding for {input_file_path}: {ve}. Output may be incorrect.",
                    file=sys.stderr,
                )
                # final_decoded_data remains intermediate_binary_data if Hamming fails critically

        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
        with open(output_file_path, "wb") as f_out:
            f_out.write(final_decoded_data)

        print(f"Successfully decoded '{input_file_path}' to '{output_file_path}'.")

    except FileNotFoundError:
        print(f"Error for {input_file_path}: Input file not found.", file=sys.stderr)
    except IOError as e:
        print(f"Error for {input_file_path}: I/O error: {e}", file=sys.stderr)
    except Exception as e:
        print(
            f"Error for {input_file_path}: Unexpected error during decoding: {e}",
            file=sys.stderr,
        )


# --- Helper function for single file analysis ---
def process_single_analyze(input_file_path: str, args: argparse.Namespace) -> None:
    """Analyzes a single FASTA file and prints summary statistics."""
    print(f"\nProcessing analysis for input: {input_file_path}")
    try:
        with open(input_file_path, "r", encoding="utf-8") as f_in:
            file_content_str = f_in.read()

        parsed_records = from_fasta(file_content_str)
        if not parsed_records:
            print(
                f"Error for {input_file_path}: No valid FASTA records found.",
                file=sys.stderr,
            )
            return

        if len(parsed_records) > 1:
            print(
                f"Warning for {input_file_path}: Multiple FASTA records found. Processing the first one only.",
                file=sys.stderr,
            )

        header, sequence = parsed_records[0]

        gc_content = calculate_gc_content(sequence)
        max_hp = get_max_homopolymer_length(sequence)
        window_starts, gc_values = calculate_windowed_gc_content(
            sequence,
            args.window_size,
            args.step,
        )
        avg_gc = sum(gc_values) / len(gc_values) if gc_values else 0.0

        print(f"Sequence length: {len(sequence)} nucleotides")
        print(f"GC content: {gc_content:.2%}")
        print(f"Max homopolymer length: {max_hp}")
        if gc_values:
            print(
                f"Windowed GC stats (window={args.window_size}, step={args.step}): "
                f"min={min(gc_values):.2%}, max={max(gc_values):.2%}, avg={avg_gc:.2%}"
            )
        else:
            print("Sequence shorter than window size; no windowed GC stats.")

        if getattr(args, "plot_dir", None):
            homopolymers = identify_homopolymer_regions(sequence, args.min_homopolymer)
            buf = generate_sequence_analysis_plot(
                (window_starts, gc_values),
                homopolymers,
                len(sequence),
            )
            os.makedirs(args.plot_dir, exist_ok=True)
            base_name = os.path.basename(input_file_path)
            plot_path = os.path.join(args.plot_dir, base_name + ".png")
            with open(plot_path, "wb") as f_out:
                f_out.write(buf.getvalue())
            buf.close()
            print(f"Plot saved to {plot_path}")

    except FileNotFoundError:
        print(f"Error for {input_file_path}: Input file not found.", file=sys.stderr)
    except Exception as e:
        print(
            f"Error for {input_file_path}: Unexpected error during analysis: {e}",
            file=sys.stderr,
        )


def main() -> None:
    """Parses command-line arguments and executes the requested GeneCoder command."""
    parser = argparse.ArgumentParser(
        description="GeneCoder: Encode and decode data into simulated DNA sequences."
    )
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands. Use `<command> -h` for more details.",
        required=True,
    )

    # Encode command parser
    encode_parser = subparsers.add_parser(
        "encode", help="Encode data into DNA sequences."
    )
    encode_parser.add_argument(
        "--input-files",
        type=str,
        nargs="+",
        required=True,
        help="Path(s) to the input file(s) to encode.",
    )
    encode_parser.add_argument(
        "--output-file",
        type=str,
        help="Path to save the encoded DNA sequence (for single input file).",
    )
    encode_parser.add_argument(
        "--output-dir",
        type=str,
        help="Directory to save encoded files (for multiple inputs, or single if --output-file is not set).",
    )
    encode_parser.add_argument(
        "--method",
        type=str,
        default="base4_direct",
        choices=["base4_direct", "huffman", "gc_balanced"],
        help="Encoding method to use (default: base4_direct).",
    )
    # Parity arguments for encode (Note: gc_balanced handles constraints internally, not via these CLI parity args directly)
    encode_parser.add_argument(
        "--add-parity",
        action="store_true",
        help="Add parity bits to the encoded sequence (applies to base4_direct and huffman).",
    )
    encode_parser.add_argument(
        "--k-value",
        type=int,
        default=7,
        help="Size of data blocks for parity calculation (default: 7).",
    )
    encode_parser.add_argument(
        "--parity-rule",
        type=str,
        default=PARITY_RULE_GC_EVEN_A_ODD_T,
        choices=[PARITY_RULE_GC_EVEN_A_ODD_T],  # Add more rules here in future
        help="Parity rule to use (default: GC_even_A_odd_T).",
    )
    encode_parser.add_argument(
        "--fec",
        type=str,
        default=None,
        choices=[None, "triple_repeat", "hamming_7_4"],  # Added hamming_7_4
        help="Forward Error Correction method to apply. Optional. (Note: hamming_7_4 is applied to binary data before DNA encoding; triple_repeat is applied to DNA sequence after encoding).",
    )
    encode_parser.add_argument(
        "--gc-min",
        type=float,
        default=0.45,
        help="Minimum GC content for gc_balanced encoding (default: 0.45).",
    )
    encode_parser.add_argument(
        "--gc-max",
        type=float,
        default=0.55,
        help="Maximum GC content for gc_balanced encoding (default: 0.55).",
    )
    encode_parser.add_argument(
        "--max-homopolymer",
        type=int,
        default=3,
        help="Maximum homopolymer length for gc_balanced encoding (default: 3).",
    )

    # Decode command parser
    decode_parser = subparsers.add_parser(
        "decode", help="Decode DNA sequences back to data."
    )
    decode_parser.add_argument(
        "--input-files",
        type=str,
        nargs="+",
        required=True,
        help="Path(s) to the input DNA file(s) to decode (FASTA format expected).",
    )
    decode_parser.add_argument(
        "--output-file",
        type=str,
        help="Path to save the decoded data (for single input file).",
    )
    decode_parser.add_argument(
        "--output-dir",
        type=str,
        help="Directory to save decoded files (for multiple inputs, or single if --output-file is not set).",
    )
    decode_parser.add_argument(
        "--method",
        type=str,
        default="base4_direct",
        choices=["base4_direct", "huffman", "gc_balanced"],
        help="Decoding method to use (default: base4_direct).",
    )
    # Parity arguments for decode (Note: gc_balanced handles constraints internally, not via these CLI parity args directly)
    decode_parser.add_argument(
        "--check-parity",
        action="store_true",
        help="Check parity bits during decoding (applies to base4_direct and huffman).",
    )
    decode_parser.add_argument(
        "--k-value",
        type=int,
        default=7,
        help="Size of data blocks for parity checking (default: 7).",
    )
    decode_parser.add_argument(
        "--parity-rule",
        type=str,
        default=PARITY_RULE_GC_EVEN_A_ODD_T,
        choices=[PARITY_RULE_GC_EVEN_A_ODD_T],  # Add more rules here in future
        help="Parity rule used during encoding (default: GC_even_A_odd_T).",
    )

    # Analyze command parser
    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze DNA sequence files."
    )
    analyze_parser.add_argument(
        "--input-files",
        type=str,
        nargs="+",
        required=True,
        help="Path(s) to the input DNA file(s) to analyze (FASTA format expected).",
    )
    analyze_parser.add_argument(
        "--window-size",
        type=int,
        default=50,
        help="Window size for GC content calculations (default: 50).",
    )
    analyze_parser.add_argument(
        "--step",
        type=int,
        default=10,
        help="Step size for sliding window (default: 10).",
    )
    analyze_parser.add_argument(
        "--min-homopolymer",
        type=int,
        default=3,
        help="Minimum homopolymer length to highlight in plots (default: 3).",
    )
    analyze_parser.add_argument(
        "--plot-dir", type=str, help="Directory to save analysis plots (optional)."
    )

    # Simulate-errors command parser
    sim_parser = subparsers.add_parser(
        "simulate-errors", help="Introduce random errors into a FASTA sequence."
    )
    sim_parser.add_argument(
        "--input-file", type=str, required=True, help="Path to the input FASTA file."
    )
    sim_parser.add_argument(
        "--output-file",
        type=str,
        required=True,
        help="Path to save the corrupted FASTA file.",
    )
    sim_parser.add_argument(
        "--sub-prob",
        type=float,
        default=0.01,
        help="Substitution probability per nucleotide.",
    )
    sim_parser.add_argument(
        "--ins-prob",
        type=float,
        default=0.0,
        help="Insertion probability after each nucleotide.",
    )
    sim_parser.add_argument(
        "--del-prob",
        type=float,
        default=0.0,
        help="Deletion probability per nucleotide.",
    )
    sim_parser.add_argument(
        "--seed", type=int, default=None, help="Random seed for deterministic output."
    )

    args = parser.parse_args()
    if hasattr(args, "input_files"):
        num_input_files = len(args.input_files)
    else:
        num_input_files = 1

    if args.command == "encode":
        if num_input_files > 1 and not args.output_dir:
            print(
                "Error: --output-dir is required when providing multiple input files for encoding.",
                file=sys.stderr,
            )
            sys.exit(1)
        if num_input_files == 1 and not args.output_file and not args.output_dir:
            print(
                "Error: For single input file, either --output-file or --output-dir must be specified.",
                file=sys.stderr,
            )
            sys.exit(1)
        if args.output_file and args.output_dir and num_input_files == 1:
            print(
                "Warning: Both --output-file and --output-dir provided for single input. Using --output-file.",
                file=sys.stderr,
            )

        tasks = []
        for input_file_path in args.input_files:
            output_file_path = ""
            if (
                args.output_file and num_input_files == 1
            ):  # Single input, explicit output file
                output_file_path = args.output_file
            elif (
                args.output_dir
            ):  # Output dir provided (either multiple inputs, or single input without explicit output file)
                base_name = os.path.basename(input_file_path)
                output_file_name = base_name + ".fasta"  # Default extension
                # Potentially add method/fec to filename here if desired: e.g. f"{base_name}_{args.method}{'_fec' if args.fec else ''}.fasta"
                output_file_path = os.path.join(args.output_dir, output_file_name)
            else:  # Should be caught by earlier checks, but as a safeguard
                print(
                    f"Error determining output path for {input_file_path}. Please check arguments.",
                    file=sys.stderr,
                )
                continue
            tasks.append((input_file_path, output_file_path, args))

        if num_input_files > 1:
            print(
                f"Starting batch encoding for {num_input_files} files using ThreadPoolExecutor..."
            )
            # Using max_workers=None lets ThreadPoolExecutor decide, often os.cpu_count() * 5
            # For I/O bound tasks, more workers can be beneficial.
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(8, os.cpu_count() + 4)
            ) as executor:
                futures = [
                    executor.submit(process_single_encode, task[0], task[1], task[2])
                    for task in tasks
                ]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        future.result()  # To raise exceptions if any occurred in the thread
                    except Exception as exc:
                        print(
                            f"A file processing task generated an exception: {exc}",
                            file=sys.stderr,
                        )
            print("\nBatch encoding finished.")
        else:  # Single file
            if tasks:
                process_single_encode(tasks[0][0], tasks[0][1], tasks[0][2])

    elif args.command == "decode":
        if num_input_files > 1 and not args.output_dir:
            print(
                "Error: --output-dir is required when providing multiple input files for decoding.",
                file=sys.stderr,
            )
            sys.exit(1)
        if num_input_files == 1 and not args.output_file and not args.output_dir:
            print(
                "Error: For single input file, either --output-file or --output-dir must be specified for decoding.",
                file=sys.stderr,
            )
            sys.exit(1)
        if args.output_file and args.output_dir and num_input_files == 1:
            print(
                "Warning: Both --output-file and --output-dir provided for single input decode. Using --output-file.",
                file=sys.stderr,
            )

        tasks = []
        for input_file_path in args.input_files:
            output_file_path = ""
            if args.output_file and num_input_files == 1:
                output_file_path = args.output_file
            elif args.output_dir:
                base_name = os.path.basename(input_file_path)
                # Remove .fasta or other common extensions, add _decoded.bin
                name_part, _ = os.path.splitext(base_name)
                output_file_name = name_part + "_decoded.bin"
                output_file_path = os.path.join(args.output_dir, output_file_name)
            else:  # Safeguard
                print(
                    f"Error determining output path for decoding {input_file_path}. Please check arguments.",
                    file=sys.stderr,
                )
                continue
            tasks.append((input_file_path, output_file_path, args))

        if num_input_files > 1:
            print(
                f"Starting batch decoding for {num_input_files} files using ThreadPoolExecutor..."
            )
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(8, os.cpu_count() + 4)
            ) as executor:
                futures = [
                    executor.submit(process_single_decode, task[0], task[1], task[2])
                    for task in tasks
                ]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        future.result()
                    except Exception as exc:
                        print(
                            f"A file decoding task generated an exception: {exc}",
                            file=sys.stderr,
                        )
            print("\nBatch decoding finished.")
        else:  # Single file
            if tasks:
                process_single_decode(tasks[0][0], tasks[0][1], tasks[0][2])

    elif args.command == "analyze":
        for input_file_path in args.input_files:
            process_single_analyze(input_file_path, args)

    elif args.command == "simulate-errors":
        try:
            with open(args.input_file, "r", encoding="utf-8") as f_in:
                fasta_str = f_in.read()
            records = from_fasta(fasta_str)
            if not records:
                print(
                    f"Error: No FASTA records found in {args.input_file}.",
                    file=sys.stderr,
                )
                sys.exit(1)
            header, seq = records[0]
            rng = random.Random(args.seed)
            corrupted = introduce_errors(
                seq,
                substitution_prob=args.sub_prob,
                insertion_prob=args.ins_prob,
                deletion_prob=args.del_prob,
                rng=rng,
            )
            new_header = f"{header} sub_prob={args.sub_prob} ins_prob={args.ins_prob} del_prob={args.del_prob}"
            fasta_out = to_fasta(corrupted, new_header, line_width=80)
            os.makedirs(os.path.dirname(args.output_file) or ".", exist_ok=True)
            with open(args.output_file, "w", encoding="utf-8") as f_out:
                f_out.write(fasta_out)
            print(f"Corrupted FASTA sequence written to {args.output_file}")
        except FileNotFoundError:
            print(f"Error: Input file {args.input_file} not found.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error during simulate-errors: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
