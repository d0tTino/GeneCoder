"""Encoding helpers and argument setup for GeneCoder CLI."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
from ..options import EncodingOptions
from pathlib import Path
from .options import build_encoding_options
from .shared import (
    add_io_args,
    add_stream_args,
    validate_chunk_size,
    validate_output_paths,
)
from genecoder.metrics import metrics

from genecoder.manifest import generate_manifest
from genecoder.encoders import (
    encode_base4_direct,
    encode_gc_balanced,
    encode_triple_repeat,
)
from genecoder.gc_constrained_encoder import (
    calculate_gc_content,
    DEFAULT_GC_MAX,
    DEFAULT_GC_MIN,
    DEFAULT_MAX_HOMOPOLYMER,
)
from genecoder.gc_balancer import AdvancedGCBalancer
from genecoder.hamming_codec import encode_data_with_hamming
from genecoder.plugin_manager import CODEC_REGISTRY, FEC_REGISTRY
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.formats import to_fasta, from_fasta
from genecoder.huffman_coding import encode_huffman
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T
from genecoder.utils import get_max_homopolymer_length, get_alphabet_maps
from genecoder.constraint_fixer import encode as constraint_fix_encode
from .common import run_tasks
from typing import Callable, cast

_COMPLEMENT_MAP = str.maketrans("ACGTacgt", "TGCAtgca")


def reverse_complement(seq: str) -> str:
    """Return the Watson-Crick reverse complement of ``seq``."""

    return seq.translate(_COMPLEMENT_MAP)[::-1]

# Delay importing heavy security module until needed
encrypt_data: Callable[..., bytes] | None = None
compute_checksum: Callable[[bytes], str] | None = None


def _ensure_security_loaded() -> None:
    global encrypt_data, compute_checksum
    if encrypt_data is None or compute_checksum is None:
        from genecoder.security import encrypt_data as _enc, compute_checksum as _chk
        encrypt_data = _enc
        compute_checksum = _chk

logger = logging.getLogger(__name__)

def run_encoding_pipeline(
    data: bytes, options: EncodingOptions, input_file_name: str
) -> tuple[str, str, str, bytes, int]:
    _ensure_security_loaded()
    current_input = data
    fec_padding_bits = -1
    encode_map, _ = get_alphabet_maps(options.alphabet)
    # Normalize path separators to ensure the FASTA header does not contain
    # backslashes which can appear on Windows paths.
    sanitized_name = Path(input_file_name.replace("\\", "/")).name
    header_parts = [f"method={options.method}", f"input_file={sanitized_name}"]

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
        encode_kwargs = {}
        if options.fec == "reed_solomon":
            encode_kwargs = {
                "symbol_size": options.rs_symbol_size,
                "primitive": options.rs_primitive,
            }
        current_input, info = enc["encode"](data, **encode_kwargs)
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
        raw_dna = cast(
            str,
            encode_base4_direct(
                current_input,
                add_parity=should_add_parity,
                k_value=options.k_value,
                parity_rule=options.parity_rule,
                encode_map=encode_map,
                stream=False,
            ),
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
    suppress_warnings = (
        getattr(args, "suppress_constraint_warnings", False)
        or os.getenv("GENECODER_DISABLE_CONSTRAINT_WARNINGS", "").lower()
        in {"1", "true"}
    )
    try:
        if args.stream and args.method == "base4_direct" and args.fec is None:
            sanitized_name = os.path.basename(input_file_path.replace("\\", "/"))
            header = f"method=base4_direct input_file={sanitized_name}"
            if args.add_parity:
                header += f" parity_k={args.k_value} parity_rule={args.parity_rule}"
            from genecoder.streaming import stream_encode_file
            manifest_path = os.path.splitext(output_file_path)[0] + ".stream.manifest"

            total_len = stream_encode_file(
                input_file_path,
                output_file_path,
                header=header,
                chunk_size=args.chunk_size,
                manifest_path=manifest_path,
                resume=args.resume,
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

            if getattr(args, "mirror", False) and dna_sequence:
                rc_seq = reverse_complement(dna_sequence)
                rc_header = f"{header} mirror=rc"
                with open(output_file_path, "a", encoding="utf-8") as f_out:
                    f_out.write(to_fasta(rc_seq, rc_header, line_width=80))
                parsed_records.append((rc_header, rc_seq))

            final_gc = calculate_gc_content(dna_sequence)
            final_hp = get_max_homopolymer_length(dna_sequence)
            gc_default_bad = final_gc < DEFAULT_GC_MIN or final_gc > DEFAULT_GC_MAX
            hp_default_bad = final_hp > DEFAULT_MAX_HOMOPOLYMER
            logger.info(f"Final GC content: {final_gc:.2%}")
            logger.info(f"Final max homopolymer length: {final_hp}")
            if not suppress_warnings:
                if gc_default_bad:
                    logger.warning(
                        "GC content %.2f%% outside recommended range [%.2f%%, %.2f%%]",
                        final_gc * 100,
                        DEFAULT_GC_MIN * 100,
                        DEFAULT_GC_MAX * 100,
                    )
                if hp_default_bad:
                    logger.warning(
                        "Max homopolymer length %d exceeds recommended limit %d",
                        final_hp,
                        DEFAULT_MAX_HOMOPOLYMER,
                    )
                if not (args.gc_min <= final_gc <= args.gc_max):
                    logger.warning(
                        "Final GC content %.2f%% outside requested range [%.2f%%, %.2f%%]",
                        final_gc * 100,
                        args.gc_min * 100,
                        args.gc_max * 100,
                    )
                if final_hp > args.max_homopolymer:
                    logger.warning(
                        "Final max homopolymer length %d exceeds limit %d",
                        final_hp,
                        args.max_homopolymer,
                    )

            return os.path.basename(input_file_path), dna_sequence

        with open(input_file_path, "rb") as f_in:
            plaintext_data = f_in.read()

        data_for_encoding = plaintext_data
        _key_bytes = None
        if getattr(args, "key", None):
            with open(args.key, "rb") as kf:
                _key_bytes = kf.read()
        if getattr(args, "encrypt", False):
            if _key_bytes is None:
                logger.error("Encryption key required when --encrypt is used.")
                raise SystemExit(1)
            _ensure_security_loaded()
            assert encrypt_data is not None
            data_for_encoding = encrypt_data(plaintext_data, key=_key_bytes)

        checksum: str | None = None
        if getattr(args, "checksum", False):
            _ensure_security_loaded()
            assert compute_checksum is not None
            checksum = compute_checksum(plaintext_data)

        options = build_encoding_options(args)
        header_name = os.path.basename(input_file_path.replace("\\", "/"))
        if getattr(args, "file_type", None):
            stem = Path(header_name).stem
            header_name = f"{stem}.{args.file_type}"

        (
            final_encoded_dna_sequence,
            fasta_header,
            raw_encoded_dna,
            current_input_data,
            fec_padding_bits,
        ) = run_encoding_pipeline(
            data_for_encoding, options, header_name
        )

        auto_fix_metrics: dict[str, float] = {}
        if getattr(args, "auto_fix", True) and os.getenv("GENECODER_DISABLE_FIX") not in {"1", "true", "True"}:
            target_dna = raw_encoded_dna
            if getattr(args, "fix_chisel", False) and "dnachisel_fixer" in CODEC_REGISTRY:
                from genecoder.dnachisel_fixer import fix_sequence_dnachisel

                target_dna = fix_sequence_dnachisel(
                    target_dna,
                    gc_min=args.gc_min,
                    gc_max=args.gc_max,
                    max_homopolymer=args.max_homopolymer,
                )
                fix_metrics = {
                    "gc_content": calculate_gc_content(target_dna),
                    "max_homopolymer": get_max_homopolymer_length(target_dna),
                }
            else:
                target_dna, fix_metrics = constraint_fix_encode(
                    target_dna,
                    gc_min=args.gc_min,
                    gc_max=args.gc_max,
                    max_homopolymer=args.max_homopolymer,
                )
            auto_fix_metrics = {
                "fixed_gc": fix_metrics["gc_content"],
                "fixed_max_homopolymer": fix_metrics["max_homopolymer"],
            }

            if args.fec == "triple_repeat":
                final_encoded_dna_sequence = encode_triple_repeat(target_dna)
            else:
                final_encoded_dna_sequence = target_dna

        if checksum:
            fasta_header = f"{fasta_header} checksum={checksum}"

        fasta_output = to_fasta(final_encoded_dna_sequence, fasta_header, line_width=80)
        if getattr(args, "mirror", False):
            rc_seq = reverse_complement(final_encoded_dna_sequence)
            rc_header = f"{fasta_header} mirror=rc"
            fasta_output += to_fasta(rc_seq, rc_header, line_width=80)

        os.makedirs(os.path.dirname(output_file_path) or ".", exist_ok=True)
        with open(output_file_path, "w", encoding="utf-8") as f_out:
            f_out.write(fasta_output)

        if getattr(args, "mirror", False):
            try:
                from genecoder.helix_view import show_helix_ui

                rc_seq = reverse_complement(final_encoded_dna_sequence)
                show_helix_ui(final_encoded_dna_sequence, strand2_sequence=rc_seq)
            except Exception as exc:  # pragma: no cover - optional GUI
                logger.warning("Could not launch helix viewer: %s", exc)

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

        final_gc = calculate_gc_content(final_encoded_dna_sequence)
        final_hp = get_max_homopolymer_length(final_encoded_dna_sequence)
        gc_default_bad = final_gc < DEFAULT_GC_MIN or final_gc > DEFAULT_GC_MAX
        hp_default_bad = final_hp > DEFAULT_MAX_HOMOPOLYMER
        if not suppress_warnings:
            if gc_default_bad:
                logger.warning(
                    "GC content %.2f%% outside recommended range [%.2f%%, %.2f%%]",
                    final_gc * 100,
                    DEFAULT_GC_MIN * 100,
                    DEFAULT_GC_MAX * 100,
                )
            if hp_default_bad:
                logger.warning(
                    "Max homopolymer length %d exceeds recommended limit %d",
                    final_hp,
                    DEFAULT_MAX_HOMOPOLYMER,
                )

        metrics = {
            "original_size": original_size_bytes,
            "dna_length": final_encoded_length_nucleotides,
            "compression_ratio": compression_ratio,
            "bits_per_nt": bits_per_nucleotide,
            "final_gc": final_gc,
            "final_max_homopolymer": final_hp,
            "gc_exceeds_default": gc_default_bad,
            "homopolymer_exceeds_default": hp_default_bad,
        }
        metrics.update(auto_fix_metrics)

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

        logger.info(f"Final GC content: {final_gc:.2%}")
        logger.info(f"Final max homopolymer length: {final_hp}")
        if not suppress_warnings:
            if not (args.gc_min <= final_gc <= args.gc_max):
                logger.warning(
                    "Final GC content %.2f%% outside requested range [%.2f%%, %.2f%%]",
                    final_gc * 100,
                    args.gc_min * 100,
                    args.gc_max * 100,
                )
            if final_hp > args.max_homopolymer:
                logger.warning(
                    "Final max homopolymer length %d exceeds limit %d",
                    final_hp,
                    args.max_homopolymer,
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
    add_io_args(parser, command="encode")
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
    chan_choices = sorted(SIMULATOR_REGISTRY.keys()) or None
    parser.add_argument(
        "--channel",
        type=str,
        default=None,
        choices=chan_choices,
        help="Channel simulator to apply.",
    )
    parser.add_argument(
        "--rs-symbol-size",
        type=int,
        default=None,
        help=(
            "Symbol size (c_exp) for Reed-Solomon FEC. Ignored unless --fec"
            " reed_solomon."
        ),
    )
    parser.add_argument(
        "--rs-primitive",
        type=lambda x: int(x, 0),
        default=None,
        help=(
            "Primitive polynomial for Reed-Solomon FEC. Provide as integer or"
            " 0x-prefixed hex. Ignored unless --fec reed_solomon."
        ),
    )
    parser.add_argument(
        "--gc-min",
        type=float,
        default=0.45,
        help=(
            "Minimum GC content for gc_balanced encoding and constraint fixing "
            "(default: 0.45)."
        ),
    )
    parser.add_argument(
        "--gc-max",
        type=float,
        default=0.55,
        help=(
            "Maximum GC content for gc_balanced encoding and constraint fixing "
            "(default: 0.55)."
        ),
    )
    parser.add_argument(
        "--max-homopolymer",
        type=int,
        default=3,
        help=(
            "Maximum homopolymer length for gc_balanced encoding and constraint "
            "fixing (default: 3)."
        ),
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
        help="Encrypt input bytes before encoding (requires --key).",
    )
    parser.add_argument(
        "--key",
        type=str,
        help="Path to file containing encryption key bytes (required with --encrypt).",
    )
    parser.add_argument(
        "--checksum",
        action="store_true",
        help="Store checksum of plaintext in the FASTA header.",
    )
    add_stream_args(parser)
    parser.add_argument(
        "--file-type",
        type=str,
        choices=["jpg", "png", "pdf", "txt"],
        help="File type to record in the FASTA header when inferring output paths.",
    )
    parser.add_argument(
        "--auto-ext",
        action="store_true",
        help="Automatically append a .dna suffix to output files.",
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
    parser.add_argument(
        "--mirror",
        action="store_true",
        help="Also output the reverse-complement sequence and launch the visualizer.",
    )
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="Automatically fix GC and homopolymer constraints before synthesis.",
    )
    parser.add_argument(
        "--fix-chisel",
        action="store_true",
        help="Use DNA Chisel for constraint fixing when available.",
    )
    parser.add_argument(
        "--suppress-constraint-warnings",
        action="store_true",
        help="Suppress warnings when results exceed default GC or homopolymer limits.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for random components to ensure reproducible runs.",
    )
    parser.set_defaults(func=_handle_command)


def encode_files(args: argparse.Namespace) -> list[tuple[str, str] | None]:
    """Encode files according to ``args`` and return CSV rows."""

    validate_chunk_size(args)
    validate_output_paths(
        args,
        command="encoding",
        header_getter=None,
        allow_capsule=True,
    )
    if getattr(args, "channel", None) is not None:
        if args.channel not in SIMULATOR_REGISTRY:
            logger.error("Unknown channel: %s", args.channel)
            raise SystemExit(1)
        SIMULATOR_REGISTRY[args.channel]
    num_input_files = len(args.input_files)

    tasks = []
    csv_rows: list[tuple[str, str]] = []
    for input_file_path in args.input_files:
        output_file_path = ""
        if args.output_file and num_input_files == 1:
            output_file_path = args.output_file
            if args.auto_ext and not output_file_path.endswith(".dna"):
                output_file_path += ".dna"
        elif args.output_dir:
            base_name = os.path.basename(input_file_path)
            if args.auto_ext:
                output_file_name = base_name + ".dna"
            else:
                output_file_name = base_name + ".fasta"
            output_file_path = os.path.join(args.output_dir, output_file_name)
        elif getattr(args, "file_type", None):
            output_file_path = f"{input_file_path}.{args.file_type}.dna"
        else:
            logger.error(
                f"Error determining output path for {input_file_path}. Please check arguments."
            )
            continue
        tasks.append((input_file_path, output_file_path, args))

    results = run_tasks(
        tasks, process_single_encode, description="encoding", collect_results=True
    )
    if args.export_csv:
        csv_rows.extend([res for res in results if res])

    if args.export_csv and csv_rows:
        os.makedirs(os.path.dirname(args.export_csv) or ".", exist_ok=True)
        with open(args.export_csv, "w", newline="", encoding="utf-8") as csv_f:
            writer = csv.writer(csv_f)
            writer.writerow(["Name", "Sequence"])
            writer.writerows(csv_rows)
        logger.info(f"CSV order file written to {args.export_csv}")

    metrics.increment("encode_runs")
    return results


def _handle_command(args: argparse.Namespace) -> None:
    if args.seed is not None:
        os.environ["GENECODER_SIM_SEED"] = str(args.seed)
    encode_files(args)

