from __future__ import annotations

import argparse
import json
import sys

from genecoder.app_helpers import EncodeResult, DecodeResult
from genecoder import report as report_module


def register_subcommand(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "report", help="Generate a Markdown or HTML report from a JSON result."
    )
    parser.add_argument("--input-json", type=str, required=True, help="Path to JSON file with result data")
    parser.add_argument(
        "--type",
        choices=["encode", "decode"],
        required=True,
        help="Indicates whether the input data is from an encode or decode operation",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "html"],
        default="markdown",
        help="Output format for the report",
    )
    parser.add_argument("--output-file", type=str, help="Path to write the report. Defaults to stdout")
    parser.set_defaults(func=_handle_command)


def _handle_command(args: argparse.Namespace) -> None:
    with open(args.input_json, "r") as fh:
        data = json.load(fh)

    if args.type == "encode":
        result = EncodeResult(**data)
        if args.format == "markdown":
            report_text = report_module.encode_to_markdown(result)
        else:
            report_text = report_module.encode_to_html(result)
    else:
        result = DecodeResult(**data)
        if args.format == "markdown":
            report_text = report_module.decode_to_markdown(result)
        else:
            report_text = report_module.decode_to_html(result)

    if args.output_file:
        with open(args.output_file, "w") as fh:
            fh.write(report_text)
    else:
        sys.stdout.write(report_text)
