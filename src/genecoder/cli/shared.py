"""Shared CLI utilities for argument setup and validation."""

from __future__ import annotations

import argparse
import logging
from typing import Callable

logger = logging.getLogger(__name__)


def add_io_args(
    parser: argparse.ArgumentParser,
    *,
    command: str,
) -> None:
    """Add common input and output arguments to ``parser``."""
    if command == "encode":
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
            help=(
                "Directory to save encoded files (for multiple inputs, or single if"
                " --output-file is not set)."
            ),
        )
    else:  # decode
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
            help=(
                "Directory to save decoded files (for multiple inputs, or single if"
                " --output-file is not set)."
            ),
        )


def add_stream_args(parser: argparse.ArgumentParser) -> None:
    """Add streaming related arguments to ``parser``."""
    parser.add_argument(
        "--stream", action="store_true", help="Stream process large files (base4_direct only)."
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1_000_000,
        help="Chunk size in bytes for streaming (default: 1000000).",
    )
    parser.add_argument(
        "--resume", action="store_true", help="Resume a previous interrupted streaming job."
    )


def add_single_io_args(
    parser: argparse.ArgumentParser,
    *,
    input_help: str,
    output_help: str,
) -> None:
    """Add single ``--input-file`` and ``--output-file`` arguments."""
    parser.add_argument("--input-file", required=True, type=str, help=input_help)
    parser.add_argument("--output-file", required=True, type=str, help=output_help)


def validate_chunk_size(args: argparse.Namespace) -> None:
    """Validate that ``--chunk-size`` is positive."""
    if getattr(args, "chunk_size", 1) <= 0:
        logger.error("Error: --chunk-size must be a positive integer.")
        raise SystemExit(1)


def validate_output_paths(
    args: argparse.Namespace,
    *,
    command: str,
    header_getter: Callable[[str], str | None] | None = None,
    allow_capsule: bool = False,
) -> None:
    """Validate output path arguments for encode/decode commands."""
    num_input_files = len(args.input_files)
    if num_input_files > 1 and not args.output_dir and not getattr(args, "file_type", None):
        logger.error(
            f"Error: --output-dir is required when providing multiple input files for {command} unless --file-type is used."
        )
        raise SystemExit(1)
    if (
        num_input_files == 1
        and not args.output_file
        and not args.output_dir
        and not getattr(args, "file_type", None)
        and (header_getter is None or header_getter(args.input_files[0]) is None)
    ):
        if command == "encoding":
            msg = "Error: For single input file, either --output-file or --output-dir must be specified unless --file-type is used."
        else:
            msg = (
                "Error: For single input file, either --output-file or --output-dir must be specified for decoding unless the file type can be inferred."
            )
        logger.error(msg)
        raise SystemExit(1)
    if allow_capsule and getattr(args, "capsule", None) and num_input_files != 1:
        logger.error("Error: --capsule can only be used with a single input file.")
        raise SystemExit(1)
    if args.output_file and args.output_dir and num_input_files == 1:
        logger.warning(
            f"Warning: Both --output-file and --output-dir provided for single input {command}. Using --output-file."
        )

