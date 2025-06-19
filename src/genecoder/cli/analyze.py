"""Analysis helpers and argument setup for GeneCoder CLI."""

from __future__ import annotations

import argparse
import logging
import os

from genecoder.formats import from_fasta
from genecoder.plotting import (
    calculate_windowed_gc_content,
    identify_homopolymer_regions,
    generate_sequence_analysis_plot,
)
from genecoder.utils import get_max_homopolymer_length
from genecoder.encoders import calculate_gc_content
from genecoder.synthesis import SynthesisConstraints

logger = logging.getLogger(__name__)


def process_single_analyze(input_file_path: str, args: argparse.Namespace) -> None:
    logger.info(f"\nProcessing analysis for input: {input_file_path}")
    try:
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

        header, sequence = parsed_records[0]

        gc_content = calculate_gc_content(sequence)
        max_hp = get_max_homopolymer_length(sequence)
        window_starts, gc_values = calculate_windowed_gc_content(
            sequence,
            args.window_size,
            args.step,
        )
        avg_gc = sum(gc_values) / len(gc_values) if gc_values else 0.0

        logger.info(f"Sequence length: {len(sequence)} nucleotides")
        logger.info(f"GC content: {gc_content:.2%}")
        logger.info(f"Max homopolymer length: {max_hp}")

        constraints = SynthesisConstraints()
        if len(sequence) < constraints.min_length or len(sequence) > constraints.max_length:
            logger.warning(
                f"Warning for {input_file_path}: Sequence length {len(sequence)} is outside the synthesis range {constraints.min_length}-{constraints.max_length}."
            )
        if max_hp > constraints.max_homopolymer:
            logger.warning(
                f"Warning for {input_file_path}: Maximum homopolymer {max_hp} exceeds allowed {constraints.max_homopolymer}."
            )
        if gc_values:
            logger.info(
                f"Windowed GC stats (window={args.window_size}, step={args.step}): min={min(gc_values):.2%}, max={max(gc_values):.2%}, avg={avg_gc:.2%}"
            )
        else:
            logger.info("Sequence shorter than window size; no windowed GC stats.")

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
            logger.info(f"Plot saved to {plot_path}")

    except FileNotFoundError:
        logger.error(f"Error for {input_file_path}: Input file not found.")
    except Exception as e:
        logger.error(
            f"Error for {input_file_path}: Unexpected error during analysis: {e}"
        )


def register_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("analyze", help="Analyze DNA sequence files.")
    parser.add_argument(
        "--input-files",
        type=str,
        nargs="+",
        required=True,
        help="Path(s) to the input DNA file(s) to analyze (FASTA format expected).",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=50,
        help="Window size for GC content calculations (default: 50).",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=10,
        help="Step size for sliding window (default: 10).",
    )
    parser.add_argument(
        "--min-homopolymer",
        type=int,
        default=3,
        help="Minimum homopolymer length to highlight in plots (default: 3).",
    )
    parser.add_argument(
        "--plot-dir", type=str, help="Directory to save analysis plots (optional)."
    )
    parser.set_defaults(func=_handle_command)


def _handle_command(args: argparse.Namespace) -> None:
    for input_file_path in args.input_files:
        process_single_analyze(input_file_path, args)

