"""Encoding helpers and argument setup for GeneCoder CLI."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import logging
import os
from dataclasses import dataclass

from genecoder.manifest import generate_manifest
from genecoder.encoders import (
    encode_base4_direct,
    encode_gc_balanced,
    calculate_gc_content,
    encode_triple_repeat,
)
from genecoder.gc_balancer import AdvancedGCBalancer
from genecoder.hamming_codec import encode_data_with_hamming
from genecoder.plugins import FEC_REGISTRY
from genecoder.formats import to_fasta, from_fasta
from genecoder.huffman_coding import encode_huffman
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T
from genecoder.utils import get_max_homopolymer_length, get_alphabet_maps
from genecoder.security import encrypt_data, compute_checksum

logger = logging.getLogger(__name__)


@dataclass
class EncodingOptions:
    method: str
    add_parity: bool
    k_value: int
    parity_rule: str
    fec: str | None
    gc_min: float
    gc_max: float
    max_homopolymer: int
    alphabet: str = "base4"


def build_encoding_options(args: argparse.Namespace) -> EncodingOptions:
    return EncodingOptions(
        method=args.method,
        add_parity=args.add_parity,
        k_value=args.k_value,
        parity_rule=args.parity_rule,
        fec=args.fec,
        gc_min=args.gc_min,
        gc_max=args.gc_max,
        max_homopolymer=args.max_homopolymer,
        alphabet=getattr(args, "alphabet", "base4"),
    )


def run_encoding_pipeline(
    data: bytes, options: EncodingOptions, input_file_name: str
) -> tuple[str, str, str, bytes, int]:
    current_input = data
    fec_padding_bits = -1
    encode_map, _ = get_alphabet_maps(options.alphabet)
    header_parts = [f"method={options.method}", f"input_file={input_file_name}"]

    if options.fec == "hamming_7_4":
        if options.add_parity:
            logger.warning(
                f"Warning for {input_file_name}: --add-parity is ignored when Hamming(7,4) FEC is applied to binary data."
            )
        current_input, fec_padding_bits = encode_data_with_hamming(data)
        header_parts.append("fec=hamming_7_4")
        header_parts.append(f"fec_padding_bits={fec_padding_bits}")
        logger.info(
            f"Applied Hamming(7,4) FEC to {input_file_name}. Original binary size: {len(data)}, Hamming encoded binary size: {len(current_input)} (padding bits: {fec_padding_bits})."
        )
    elif options.fec and options.fec in FEC_REGISTRY:
        if options.add_parity:
            logger.warning(
                f"Warning for {input_file_name}: --add-parity is ignored when {options.fec} FEC is applied to binary data."
            )
        enc = FEC_REGISTRY[options.fec]
        current_input, info = enc["encode"](data)
        header_parts.append(f"fec={options.fec}")
        if info is not None:
            import base64
            import json

            encoded_info = base64.b64encode(json.dumps(info).encode()).decode()
            header_parts.append(f"fec_info={encoded_info}")
        logger.info(
            f"Applied {options.fec} FEC to {input_file_name}. Original binary size: {len(data)}, encoded size: {len(current_input)}."
        )
    raw_dna = ""
    disabled_fec = {"hamming_7_4", *FEC_REGISTRY.keys()}
    should_add_parity = options.add_parity and (
        options.fec is None or options.fec not in disabled_fec
    )

    if options.method == "base4_direct":
        if should_add_parity and options.k_value <= 0:
            raise ValueError("Parity k-value must be positive.")
        raw_dna = encode_base4_direct(
            current_input,
            add_parity=should_add_parity,
            k_value=options.k_value,
            parity_rule=options.parity_rule,
            encode_map=encode_map,
        )
        if should_add_parity:
            header_parts.extend(
                [f"parity_k={options.k_value}", f"parity_rule={options.parity_rule}"]
            )
    elif options.method == "huffman":
        if should_add_parity and options.k_value <= 0:
            raise ValueError("Parity k-value must be positive for Huffman.")
        raw_dna, huffman_table, num_padding_bits = encode_huffman(
            current_input,
            add_parity=should_add_parity,
            k_value=options.k_value,
            parity_rule=options.parity_rule,
            encode_map=encode_map,
        )
        serializable_table = {str(k): v for k, v in huffman_table.items()}
        huffman_params = {"table": serializable_table, "padding": num_padding_bits}
        header_parts.append(f"huffman_params={json.dumps(huffman_params)}")
        if should_add_parity:
            header_parts.extend(
                [f"parity_k={options.k_value}", f"parity_rule={options.parity_rule}"]
            )
    elif options.method == "gc_balanced":
        if should_add_parity:
            logger.warning(
                f"Warning for {input_file_name}: --add-parity not directly used by 'gc_balanced' core logic."
            )
        raw_dna = encode_gc_balanced(
            current_input,
            options.gc_min,
            options.gc_max,
            options.max_homopolymer,
        )
        header_parts.extend(
            [
                f"gc_min={options.gc_min}",
                f"gc_max={options.gc_max}",
                f"max_homopolymer={options.max_homopolymer}",
            ]
        )
    elif options.method == "gc_balanced_advanced":
        if should_add_parity:
            logger.warning(
                f"Warning for {input_file_name}: --add-parity not used by 'gc_balanced_advanced'."
            )
        balancer = AdvancedGCBalancer(
            options.gc_min,
            options.gc_max,
            options.max_homopolymer,
        )
        raw_dna = balancer.encode(current_input)
        header_parts.extend(
            [
                f"gc_min={options.gc_min}",
                f"gc_max={options.gc_max}",
                f"max_homopolymer={options.max_homopolymer}",
            ]
        )
    else:
        raise ValueError(f"Unknown encoding method '{options.method}'.")

    final_dna = raw_dna
    if options.fec == "triple_repeat":
        final_dna = encode_triple_repeat(raw_dna)
        header_parts.append("fec=triple_repeat")
        logger.info(
            f"Applied Triple-Repeat FEC to {input_file_name}. DNA length before: {len(raw_dna)}, after: {len(final_dna)}."
        )
    elif options.fec:
        logger.warning(
            f"Warning for {input_file_name}: Unknown FEC method '{options.fec}'. No DNA-level FEC applied."
        )

    return final_dna, " ".join(header_parts), raw_dna, current_input, fec_padding_bits


def process_single_encode(
    input_file_path: str, output_file_path: str, args: argparse.Namespace
) -> tuple[str, str] | None:
    logger.info(
        f"\nProcessing encode for input: {input_file_path} -> output: {output_file_path}"
    )
    try:
        if args.stream and args.method == "base4_direct" and args.fec is None:
            header = f"method=base4_direct input_file={os.path.basename(input_file_path)}"
            if args.add_parity:
                header += f" parity_k={args.k_value} parity_rule={args.parity_rule}"
            from genecoder.streaming import stream_encode_file

            total_len = stream_encode_file(
                input_file_path,
                output_file_path,
                header=header,
                add_parity=args.add_parity,
                k_value=args.k_value,
                parity_rule=args.parity_rule,
                alphabet=args.alphabet,
            )

            original_size_bytes = os.path.getsize(input_file_path)
            dna_equivalent_bytes = total_len * 0.25
            compression_ratio = (
                original_size_bytes / dna_equivalent_bytes
                if dna_equivalent_bytes > 0
                else (float("inf") if original_size_bytes > 0 else 0.0)
            )
            bits_per_nucleotide = (
                (original_size_bytes * 8) / total_len if total_len else 0.0
            )

            logger.info(f"\n--- Encoding Metrics for {input_file_path} ---")
            logger.info(f"Original file size: {original_size_bytes} bytes")
            logger.info(
                f"Final Encoded DNA length: {total_len} nucleotides (streamed)"
            )
            logger.info(
                f"Compression ratio: {compression_ratio:.2f} (original bytes / final DNA bytes equivalent)"
            )
            logger.info(
                f"Bits per nucleotide: {bits_per_nucleotide:.2f} bits/nt"
            )
            logger.info("----------------------")
            logger.info(
                f"Successfully encoded '{input_file_path}' to '{output_file_path}' using streaming."
            )

            with open(output_file_path, "r", encoding="utf-8") as f_out:
                fasta_content = f_out.read()

            parsed_records = from_fasta(fasta_content)
            dna_sequence = parsed_records[0][1] if parsed_records else ""

            return os.path.basename(input_file_path), dna_sequence

        with open(input_file_path, "rb") as f_in:
            plaintext_data = f_in.read()

        data_for_encoding = plaintext_data
        key_bytes = None
        if getattr(args, "key", None):
            with open(args.key, "rb") as kf:
                key_bytes = kf.read()
        if getattr(args, "encrypt", False):
            data_for_encoding = encrypt_data(plaintext_data, key=key_bytes)

        checksum: str | None = None
        if getattr(args, "checksum", False):
            checksum = compute_checksum(plaintext_data)

        options = build_encoding_options(args)
        (
            final_encoded_dna_sequence,
            fasta_header,
            raw_encoded_dna,
            current_input_data,
            fec_padding_bits,
        ) = run_encoding_pipeline(
            data_for_encoding, options, os.path.basename(input_file_path)
        )

        if checksum:
            fasta_header = f"{fasta_header} checksum={checksum}"

        fasta_output = to_fasta(final_encoded_dna_sequence, fasta_header, line_width=80)

        os.makedirs(os.path.dirname(output_file_path) or ".", exist_ok=True)
        with open(output_file_path, "w", encoding="utf-8") as f_out:
            f_out.write(fasta_output)

        if getattr(args, "capsule", None):
            from genecoder.cache_dna import write_capsule

            metadata = {
                "input_file": os.path.basename(input_file_path),
                "method": args.method,
                "fec": args.fec,
            }
            write_capsule(
                final_encoded_dna_sequence,
                fasta_header,
                metadata,
                args.capsule,
            )
            logger.info(f"Capsule written to {args.capsule}")

        original_size_bytes = len(plaintext_data)
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

        metrics = {
            "original_size": original_size_bytes,
            "dna_length": final_encoded_length_nucleotides,
            "compression_ratio": compression_ratio,
            "bits_per_nt": bits_per_nucleotide,
        }

        logger.info(f"\n--- Encoding Metrics for {input_file_path} ---")
        logger.info(f"Original file size: {original_size_bytes} bytes")
        if args.fec == "hamming_7_4":
            logger.info(
                f"Binary size after Hamming(7,4) FEC: {len(current_input_data)} bytes (padding: {fec_padding_bits} bits)"
            )
        logger.info(
            f"Final Encoded DNA length: {final_encoded_length_nucleotides} nucleotides (after any DNA-level FEC like triple_repeat)"
        )
        logger.info(
            f"Compression ratio: {compression_ratio:.2f} (original bytes / final DNA bytes equivalent)"
        )
        logger.info(
            f"Bits per nucleotide: {bits_per_nucleotide:.2f} bits/nt (based on original data and final DNA length)"
        )

        if args.method == "gc_balanced":
            gc_balanced_payload_dna = (
                raw_encoded_dna[1:] if len(raw_encoded_dna) > 0 else ""
            )
            logger.info(
                f"Actual GC content (gc_balanced payload, pre-DNA FEC): {calculate_gc_content(gc_balanced_payload_dna):.2%}"
            )
            logger.info(
                f"Actual max homopolymer length (gc_balanced payload, pre-DNA FEC): {get_max_homopolymer_length(gc_balanced_payload_dna)}"
            )
            metrics["actual_gc"] = calculate_gc_content(gc_balanced_payload_dna)
            metrics["max_homopolymer"] = get_max_homopolymer_length(
                gc_balanced_payload_dna
            )
        logger.info("----------------------")
        logger.info(f"Successfully encoded '{input_file_path}' to '{output_file_path}'.")

        manifest = generate_manifest(os.path.basename(input_file_path), options, metrics)
        manifest_path = os.path.splitext(output_file_path)[0] + ".manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as mf:
            json.dump(manifest, mf, indent=2)

        return os.path.basename(input_file_path), final_encoded_dna_sequence

    except FileNotFoundError:
        logger.error(f"Error for {input_file_path}: Input file not found.")
    except IOError as e:
        logger.error(f"Error for {input_file_path}: I/O error: {e}")
    except ImportError as exc:
        logger.error("Error for %s: %s", input_file_path, exc)
        raise SystemExit(1)
    except Exception:
        logger.exception(
            "Error for %s: Unexpected error during encoding", input_file_path
        )
        raise
    return None


def register_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("encode", help="Encode data into DNA sequences.")
    parser.add_argument(
        "--input-files",
        type=str,
        nargs="+",
        required=True,
        help="Path(s) to the input file(s) to encode.",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        help="Path to save the encoded DNA sequence (for single input file).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Directory to save encoded files (for multiple inputs, or single if --output-file is not set).",
    )
    parser.add_argument(
        "--method",
        type=str,
        default="base4_direct",
        choices=["base4_direct", "huffman", "gc_balanced", "gc_balanced_advanced"],
        help="Encoding method to use (default: base4_direct).",
    )
    parser.add_argument(
        "--add-parity",
        action="store_true",
        help="Add parity bits to the encoded sequence (applies to base4_direct and huffman).",
    )
    parser.add_argument(
        "--k-value",
        type=int,
        default=7,
        help="Size of data blocks for parity calculation (default: 7).",
    )
    parser.add_argument(
        "--parity-rule",
        type=str,
        default=PARITY_RULE_GC_EVEN_A_ODD_T,
        choices=[PARITY_RULE_GC_EVEN_A_ODD_T],
        help="Parity rule to use (default: GC_even_A_odd_T).",
    )
    fec_choices = sorted({"triple_repeat", "hamming_7_4", *FEC_REGISTRY.keys()})
    parser.add_argument(
        "--fec",
        type=str,
        default=None,
        choices=fec_choices,
        help="Forward Error Correction method to apply.",
    )
    parser.add_argument(
        "--gc-min",
        type=float,
        default=0.45,
        help="Minimum GC content for gc_balanced encoding (default: 0.45).",
    )
    parser.add_argument(
        "--gc-max",
        type=float,
        default=0.55,
        help="Maximum GC content for gc_balanced encoding (default: 0.55).",
    )
    parser.add_argument(
        "--max-homopolymer",
        type=int,
        default=3,
        help="Maximum homopolymer length for gc_balanced encoding (default: 3).",
    )
    parser.add_argument(
        "--alphabet",
        type=str,
        default="base4",
        choices=["base4", "base5", "base6"],
        help=(
            "Alphabet mapping to use. base5 and base6 simply remap the ACGT"
            " symbols and do not increase capacity (default: base4)."
        ),
    )
    parser.add_argument(
        "--encrypt",
        action="store_true",
        help="Encrypt input bytes before encoding.",
    )
    parser.add_argument(
        "--key",
        type=str,
        help="Path to file containing encryption key bytes.",
    )
    parser.add_argument(
        "--checksum",
        action="store_true",
        help="Store checksum of plaintext in the FASTA header.",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream encode large files (base4_direct only).",
    )
    parser.add_argument(
        "--export-csv",
        type=str,
        help="Path to write a Twist/IDT order CSV with Name and Sequence columns.",
    )
    parser.add_argument(
        "--capsule",
        type=str,
        help="Write capsule JSON with header, sequence and metadata.",
    )
    parser.set_defaults(func=_handle_command)


def _handle_command(args: argparse.Namespace) -> None:
    num_input_files = len(args.input_files)
    if num_input_files > 1 and not args.output_dir:
        logger.error("Error: --output-dir is required when providing multiple input files for encoding.")
        raise SystemExit(1)
    if num_input_files == 1 and not args.output_file and not args.output_dir:
        logger.error("Error: For single input file, either --output-file or --output-dir must be specified.")
        raise SystemExit(1)
    if args.output_file and args.output_dir and num_input_files == 1:
        logger.warning("Warning: Both --output-file and --output-dir provided for single input. Using --output-file.")
    if args.capsule and num_input_files != 1:
        logger.error("Error: --capsule can only be used with a single input file.")
        raise SystemExit(1)

    tasks = []
    csv_rows: list[tuple[str, str]] = []
    for input_file_path in args.input_files:
        output_file_path = ""
        if args.output_file and num_input_files == 1:
            output_file_path = args.output_file
        elif args.output_dir:
            base_name = os.path.basename(input_file_path)
            output_file_name = base_name + ".fasta"
            output_file_path = os.path.join(args.output_dir, output_file_name)
        else:
            logger.error(f"Error determining output path for {input_file_path}. Please check arguments.")
            continue
        tasks.append((input_file_path, output_file_path, args))

    if num_input_files > 1:
        logger.info(f"Starting batch encoding for {num_input_files} files using ThreadPoolExecutor...")
        cpu_count = os.cpu_count() or 1
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, cpu_count + 4)) as executor:
            future_to_file = {executor.submit(process_single_encode, t[0], t[1], t[2]): t[0] for t in tasks}
            for future in concurrent.futures.as_completed(future_to_file):
                try:
                    res = future.result()
                    if args.export_csv and res:
                        csv_rows.append(res)
                except Exception:
                    logger.exception("A file processing task generated an exception")
        logger.info("\nBatch encoding finished.")
    else:
        if tasks:
            res = process_single_encode(tasks[0][0], tasks[0][1], tasks[0][2])
            if args.export_csv and res:
                csv_rows.append(res)

    if args.export_csv and csv_rows:
        os.makedirs(os.path.dirname(args.export_csv) or ".", exist_ok=True)
        with open(args.export_csv, "w", newline="", encoding="utf-8") as csv_f:
            writer = csv.writer(csv_f)
            writer.writerow(["Name", "Sequence"])
            writer.writerows(csv_rows)
        logger.info(f"CSV order file written to {args.export_csv}")

