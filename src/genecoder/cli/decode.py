"""Decoding helpers and argument setup for GeneCoder CLI."""

from __future__ import annotations

import argparse
import concurrent.futures
import logging
import os
import random
import re
from dataclasses import dataclass

from genecoder.encoders import decode_base4_direct, decode_gc_balanced, decode_triple_repeat
from genecoder.hamming_codec import decode_data_with_hamming
from genecoder.plugins import FEC_REGISTRY, SIMULATOR_REGISTRY
from genecoder.formats import from_fasta
from genecoder.utils import get_alphabet_maps
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T

logger = logging.getLogger(__name__)


@dataclass
class DecodingOptions:
    method: str
    check_parity: bool
    k_value: int
    parity_rule: str
    alphabet: str


def build_decoding_options(args: argparse.Namespace) -> DecodingOptions:
    return DecodingOptions(
        method=args.method,
        check_parity=args.check_parity,
        k_value=args.k_value,
        parity_rule=args.parity_rule,
        alphabet=getattr(args, "alphabet", "base4"),
    )


def run_decoding_pipeline(
    sequence: str, header: str, options: DecodingOptions, input_file_name: str
) -> bytes:
    dna_for_primary = sequence
    _, decode_map = get_alphabet_maps(options.alphabet)
    if "fec=triple_repeat" in header:
        logger.info(f"Triple-Repeat FEC detected in header for {input_file_name}.")
        if len(sequence) % 3 != 0:
            logger.warning(
                f"Warning for {input_file_name}: Sequence length {len(sequence)} is not multiple of 3 for Triple-Repeat FEC. Attempting decode."
            )
        try:
            dna_for_primary, corrected_tr, uncorr_tr = decode_triple_repeat(sequence)
            logger.info(
                f"Triple-Repeat FEC decoding for {input_file_name}: {corrected_tr} corrected, {uncorr_tr} uncorrectable errors in triplets."
            )
        except ValueError as ve:
            logger.error(
                f"Error during Triple-Repeat FEC decoding for {input_file_name}: {ve}. Using sequence as is for primary decode."
            )

    parity_errors: list[int] = []
    fec_names = [f"fec={name}" for name in FEC_REGISTRY]
    should_check_parity = (
        options.check_parity
        and not any(tag in header for tag in fec_names)
    )

    if options.method == "base4_direct":
        if should_check_parity and options.k_value <= 0:
            raise ValueError("Parity k-value must be positive for DNA-level parity.")
        binary_data, parity_errors = decode_base4_direct(
            dna_for_primary,
            check_parity=should_check_parity,
            k_value=options.k_value,
            parity_rule=options.parity_rule,
            decode_map=decode_map,
        )
    elif options.method == "gc_balanced":
        if should_check_parity:
            logger.warning(
                f"Warning for {input_file_name}: --check-parity is not applicable to 'gc_balanced' method's DNA layer."
            )
        gc_min_match = re.search(r"gc_min=([\d.]+)", header)
        gc_max_match = re.search(r"gc_max=([\d.]+)", header)
        max_hp_match = re.search(r"max_homopolymer=(\d+)", header)
        gc_min = float(gc_min_match.group(1)) if gc_min_match else None
        gc_max = float(gc_max_match.group(1)) if gc_max_match else None
        max_hp = int(max_hp_match.group(1)) if max_hp_match else None
        binary_data = decode_gc_balanced(
            dna_for_primary,
            expected_gc_min=gc_min,
            expected_gc_max=gc_max,
            expected_max_homopolymer=max_hp,
        )
    else:
        raise ValueError(f"Unknown decoding method '{options.method}'.")

    if should_check_parity and parity_errors:
        logger.warning(
            f"Warning for {input_file_name}: DNA-level parity errors in data blocks: {parity_errors}"
        )

    final_data: bytes = binary_data
    if "fec=hamming_7_4" in header:
        logger.info(f"Hamming(7,4) FEC detected in header for {input_file_name}.")
        fec_padding_bits_match = re.search(r"fec_padding_bits=(\d+)", header)
        if not fec_padding_bits_match:
            raise ValueError("'fec_padding_bits' missing in header for Hamming(7,4) FEC.")
        fec_padding_bits = int(fec_padding_bits_match.group(1))
        final_data, _ = decode_data_with_hamming(binary_data, fec_padding_bits)
    else:
        fec_match = re.search(r"fec=([\w_]+)", header)
        if fec_match:
            fec_name = fec_match.group(1)
            if fec_name in FEC_REGISTRY:
                info_match = re.search(r"fec_info=([^ ]+)", header)
                info = None
                if info_match:
                    import base64
                    import pickle

                    info = pickle.loads(base64.b64decode(info_match.group(1)))
                final_data, _ = FEC_REGISTRY[fec_name]["decode"](final_data, info)
    return final_data


def process_single_decode(
    input_file_path: str, output_file_path: str, args: argparse.Namespace
) -> None:
    logger.info(
        f"\nProcessing decode for input: {input_file_path} -> output: {output_file_path}"
    )
    try:
        if args.stream and args.method == "base4_direct":
            from genecoder.streaming import stream_decode_file

            stream_decode_file(
                input_file_path,
                output_file_path,
                check_parity=args.check_parity,
                k_value=args.k_value,
                parity_rule=args.parity_rule,
                alphabet=args.alphabet,
            )
            logger.info(
                f"Successfully decoded '{input_file_path}' to '{output_file_path}' using streaming."
            )
            return

        with open(input_file_path, "r", encoding="utf-8") as f_in:
            file_content_str = f_in.read()

        parsed_records = from_fasta(file_content_str)
        if not parsed_records:
            logger.info(
                f"Error for {input_file_path}: No valid FASTA records found."
            )
            return
        if len(parsed_records) > 1:
            logger.info(
                f"Warning for {input_file_path}: Multiple FASTA records found. Processing the first one only."
            )

        header, sequence_from_fasta = parsed_records[0]

        header_method_match = re.search(r"method=([\w_]+)", header)
        if header_method_match:
            header_method = header_method_match.group(1)
            if header_method != args.method:
                logger.info(
                    f"Error for {input_file_path}: FASTA header specifies method '{header_method}', but --method '{args.method}' was provided. Aborting."
                )
                raise SystemExit(1)

        if args.simulator in SIMULATOR_REGISTRY:
            simulate_func = SIMULATOR_REGISTRY[args.simulator]
            sequence_from_fasta = simulate_func(sequence_from_fasta)
            logger.info(
                f"Applied {args.simulator} simulator before decoding."
            )

        if args.simulate_errors > 0.0:
            from genecoder.channel_sim import simulate_errors

            seed_env = os.getenv("GENECODER_SIM_SEED")
            rng = random.Random(int(seed_env)) if seed_env is not None else random.Random()
            sequence_from_fasta = simulate_errors(
                sequence_from_fasta, args.simulate_errors, rng=rng
            )
            logger.info(
                f"Applied simulated errors (p={args.simulate_errors}) before decoding."
            )

        options = build_decoding_options(args)
        final_decoded_data = run_decoding_pipeline(
            sequence_from_fasta, header, options, os.path.basename(input_file_path)
        )

        os.makedirs(os.path.dirname(output_file_path) or ".", exist_ok=True)
        with open(output_file_path, "wb") as f_out:
            f_out.write(final_decoded_data)

        logger.info(f"Successfully decoded '{input_file_path}' to '{output_file_path}'.")

    except FileNotFoundError:
        logger.error(f"Error for {input_file_path}: Input file not found.")
    except IOError as e:
        logger.error(f"Error for {input_file_path}: I/O error: {e}")
    except Exception as e:
        logger.error(
            f"Error for {input_file_path}: Unexpected error during decoding: {e}"
        )


def register_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("decode", help="Decode DNA sequences back to data.")
    parser.add_argument(
        "--input-files",
        type=str,
        nargs="+",
        required=True,
        help="Path(s) to the input DNA file(s) to decode (FASTA format expected).",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        help="Path to save the decoded data (for single input file).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Directory to save decoded files (for multiple inputs, or single if --output-file is not set).",
    )
    parser.add_argument(
        "--method",
        type=str,
        default="base4_direct",
        choices=["base4_direct", "huffman", "gc_balanced"],
        help="Decoding method to use (default: base4_direct).",
    )
    parser.add_argument(
        "--check-parity",
        action="store_true",
        help="Check parity bits during decoding (applies to base4_direct and huffman).",
    )
    parser.add_argument(
        "--k-value",
        type=int,
        default=7,
        help="Size of data blocks for parity checking (default: 7).",
    )
    parser.add_argument(
        "--parity-rule",
        type=str,
        default=PARITY_RULE_GC_EVEN_A_ODD_T,
        choices=[PARITY_RULE_GC_EVEN_A_ODD_T],
        help="Parity rule used during encoding (default: GC_even_A_odd_T).",
    )
    parser.add_argument(
        "--alphabet",
        type=str,
        default="base4",
        choices=["base4", "base5", "base6"],
        help="Alphabet mapping used during encoding (default: base4).",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream decode large files (base4_direct only).",
    )
    parser.add_argument(
        "--simulate-errors",
        type=float,
        default=0.0,
        help="Probability of random substitution errors applied before decoding.",
    )
    sim_choices = list(sorted(SIMULATOR_REGISTRY.keys())) or ["none"]
    parser.add_argument(
        "--simulator",
        type=str,
        default="none",
        choices=sim_choices,
        help="Apply an external simulator before decoding (default: none).",
    )
    parser.set_defaults(func=_handle_command)


def _handle_command(args: argparse.Namespace) -> None:
    num_input_files = len(args.input_files)
    if num_input_files > 1 and not args.output_dir:
        logger.error(
            "Error: --output-dir is required when providing multiple input files for decoding."
        )
        raise SystemExit(1)
    if num_input_files == 1 and not args.output_file and not args.output_dir:
        logger.error(
            "Error: For single input file, either --output-file or --output-dir must be specified for decoding."
        )
        raise SystemExit(1)
    if args.output_file and args.output_dir and num_input_files == 1:
        logger.warning(
            "Warning: Both --output-file and --output-dir provided for single input decode. Using --output-file."
        )

    tasks = []
    for input_file_path in args.input_files:
        output_file_path = ""
        if args.output_file and num_input_files == 1:
            output_file_path = args.output_file
        elif args.output_dir:
            base_name = os.path.basename(input_file_path)
            name_part, _ = os.path.splitext(base_name)
            output_file_name = name_part + "_decoded.bin"
            output_file_path = os.path.join(args.output_dir, output_file_name)
        else:
            logger.error(
                f"Error determining output path for decoding {input_file_path}. Please check arguments."
            )
            continue
        tasks.append((input_file_path, output_file_path, args))

    if num_input_files > 1:
        logger.info(
            f"Starting batch decoding for {num_input_files} files using ThreadPoolExecutor..."
        )
        cpu_count = os.cpu_count() or 1
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, cpu_count + 4)) as executor:
            futures_list = [
                executor.submit(process_single_decode, task[0], task[1], task[2])
                for task in tasks
            ]
            for decode_future in concurrent.futures.as_completed(futures_list):
                try:
                    decode_future.result()
                except Exception as exc:
                    logger.error(f"A file decoding task generated an exception: {exc}")
        logger.info("\nBatch decoding finished.")
    else:
        if tasks:
            process_single_decode(tasks[0][0], tasks[0][1], tasks[0][2])

