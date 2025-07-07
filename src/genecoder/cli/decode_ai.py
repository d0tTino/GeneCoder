"""CLI for decoding data with the DNAformer model."""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os


logger = logging.getLogger(__name__)


def _handle_command(args: argparse.Namespace) -> None:
    try:
        from genecoder.dnaformer_codec import decode_data_dnaformer
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.error("DNAformer not available: %s", exc)
        raise SystemExit(1)

    with open(args.encoded, "rb") as f_in:
        data = f_in.read()
    if args.base64:
        data = base64.b64decode(data, validate=True)
    if args.info:
        with open(args.info, "r", encoding="utf-8") as f_info:
            info = json.load(f_info)
    else:
        info = {}
    decoded, corrected = decode_data_dnaformer(data, info)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "wb") as f_out:
        f_out.write(decoded)
    logger.info("Corrected %d errors", corrected)


def register_subcommand(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "decode-ai", help="Decode data using the DNAformer AI model."
    )
    parser.add_argument("--encoded", required=True, help="Path to encoded data")
    parser.add_argument(
        "--info", help="Path to JSON file with encoding info", default=None
    )
    parser.add_argument("--output", required=True, help="Path to write decoded data")
    parser.add_argument(
        "--base64",
        action="store_true",
        help="Input file contains base64 text rather than raw bytes",
    )
    parser.set_defaults(func=_handle_command)
