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
from genecoder.app import EncodeRequest, EncodeUseCase
from genecoder.encoders import encode_triple_repeat
from genecoder.gc_constrained_encoder import (
    calculate_gc_content,
    DEFAULT_GC_MAX,
    DEFAULT_GC_MIN,
    DEFAULT_MAX_HOMOPOLYMER,
)
from genecoder.plugin_manager import FEC_REGISTRY
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.formats import SequenceBatch
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T
from genecoder.utils import get_max_homopolymer_length
from genecoder.constraints import ConstraintRepairPipeline, ConstraintPolicy, RepairPolicy
from genecoder.synthesis import SynthesisConstraints
from .common import run_tasks
from typing import Callable

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
    response = EncodeUseCase().execute(
        EncodeRequest(data=data, options=options, input_name=input_file_name)
    )
    return (
        response.sequence,
        response.header,
        response.raw_sequence,
        response.transformed_input,
        response.fec_padding_bits,
    )


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
                batch_seed=getattr(args, "seed", None),
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

            batch = SequenceBatch.from_fasta(fasta_content)
            dna_sequence = batch.primary_sequence()

            if getattr(args, "mirror", False) and dna_sequence:
                rc_seq = reverse_complement(dna_sequence)
                base_header = batch.first_header() or header
                mirror_header = f"{base_header} mirror=rc"
                existing_records = [
                    (record.header, record.sequence) for record in batch.records()
                ]
                existing_records.append((mirror_header, rc_seq))
                rebuilt_batch = SequenceBatch.build(
                    existing_records,
                    batch_id=batch.batch_id or Path(sanitized_name).stem,
                    batch_seed=batch.seed,
                )
                with open(output_file_path, "w", encoding="utf-8") as f_out:
                    f_out.write(rebuilt_batch.to_fasta(line_width=80))
                batch = rebuilt_batch
                dna_sequence = batch.primary_sequence()

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
        manifest_spec = getattr(args, "fountain_manifest", None)
        if manifest_spec:
            manifest_path = Path(manifest_spec)
            input_stem = Path(input_file_path).stem.replace(" ", "_") or "batch"
            if manifest_path.is_dir() or manifest_spec.endswith(os.sep) or manifest_path.suffix == "":
                resolved = manifest_path / f"{input_stem}_droplets.json"
            elif len(getattr(args, "input_files", [])) > 1:
                resolved = manifest_path.parent / f"{input_stem}_{manifest_path.name}"
            else:
                resolved = manifest_path
            options.fountain_manifest = str(resolved)
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
            repair_profile = "solver" if getattr(args, "fix_chisel", False) else "balanced"
            policy = ConstraintPolicy(
                min_length=1,
                max_length=max(1, len(target_dna)),
                gc_min=args.gc_min,
                gc_max=args.gc_max,
                max_homopolymer=args.max_homopolymer,
                assumption_mode="repair",
                repair=RepairPolicy(enabled=True, profile=repair_profile),
            )
            repaired = ConstraintRepairPipeline(policy).run(target_dna, stage="encode")
            target_dna = repaired.sequence
            auto_fix_metrics = {
                "fixed_gc": calculate_gc_content(target_dna),
                "fixed_max_homopolymer": get_max_homopolymer_length(target_dna),
                "constraint_repair_report": {
                    "strategy": repaired.repair.strategy if repaired.repair else None,
                    "changes": len(repaired.repair.changes) if repaired.repair else 0,
                    "residual_risk": repaired.residual_risk,
                },
                "constraint_outcomes": [
                    {
                        "stage": repaired.stage,
                        "violations": {
                            "before": repaired.report_before.count,
                            "after": repaired.report_after.count,
                        },
                        "repairs_applied": len(repaired.repair.changes) if repaired.repair else 0,
                        "residual_risk": repaired.residual_risk,
                    }
                ],
            }

            if args.fec == "triple_repeat":
                final_encoded_dna_sequence = encode_triple_repeat(target_dna)
            else:
                final_encoded_dna_sequence = target_dna

        if checksum:
            fasta_header = f"{fasta_header} checksum={checksum}"

        records: list[tuple[str, str]] = [(fasta_header, final_encoded_dna_sequence)]
        if getattr(args, "mirror", False):
            rc_seq = reverse_complement(final_encoded_dna_sequence)
            records.append((f"{fasta_header} mirror=rc", rc_seq))

        batch_id = Path(header_name).stem.replace(" ", "_") or "batch"
        batch = SequenceBatch.build(
            records,
            batch_id=batch_id,
            batch_seed=getattr(args, "seed", None),
        )

        os.makedirs(os.path.dirname(output_file_path) or ".", exist_ok=True)
        with open(output_file_path, "w", encoding="utf-8") as f_out:
            f_out.write(batch.to_fasta(line_width=80))

        primary_sequence = batch.primary_sequence()
        primary_header = batch.first_header() or fasta_header

        if getattr(args, "mirror", False):
            try:
                from genecoder.helix_view import show_helix_ui

                rc_seq = reverse_complement(primary_sequence)
                show_helix_ui(primary_sequence, strand2_sequence=rc_seq)
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
                primary_sequence,
                primary_header,
                metadata,
                args.capsule,
            )
            logger.info(f"Capsule written to {args.capsule}")

        original_size_bytes = len(plaintext_data)
        final_encoded_length_nucleotides = len(primary_sequence)
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

        final_gc = calculate_gc_content(primary_sequence)
        final_hp = get_max_homopolymer_length(primary_sequence)
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

        constraint_engine = SynthesisConstraints(
            min_length=1,
            max_length=max(1, final_encoded_length_nucleotides),
            max_homopolymer=args.max_homopolymer,
            gc_min=args.gc_min,
            gc_max=args.gc_max,
        ).to_engine()
        metrics = {
            "original_size": original_size_bytes,
            "dna_length": final_encoded_length_nucleotides,
            "compression_ratio": compression_ratio,
            "bits_per_nt": bits_per_nucleotide,
            "final_gc": final_gc,
            "final_max_homopolymer": final_hp,
            "gc_exceeds_default": gc_default_bad,
            "homopolymer_exceeds_default": hp_default_bad,
            "constraint_report": constraint_engine.as_manifest_report(primary_sequence),
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

        return os.path.basename(input_file_path), primary_sequence

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
        "--fountain-chunk-size",
        type=int,
        default=4,
        help=(
            "Chunk size in bytes for Fountain droplets (default: 4). Ignored"
            " unless --fec fountain."
        ),
    )
    parser.add_argument(
        "--fountain-redundancy",
        type=float,
        default=2.0,
        help=(
            "Redundancy multiplier for Fountain droplets (default: 2.0)."
            " Ignored unless --fec fountain."
        ),
    )
    parser.add_argument(
        "--fountain-manifest",
        type=str,
        default=None,
        help=(
            "Optional path to export Fountain droplet metadata as JSON."
            " Ignored unless --fec fountain."
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
    encode_files(args)
