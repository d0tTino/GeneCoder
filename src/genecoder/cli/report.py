from __future__ import annotations

import argparse
import json
import sys

from genecoder.app_helpers import DecodeResult, EncodeResult
from genecoder import report as report_module
from genecoder.html_report import generate_html_report


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

    html_parser = subparsers.add_parser(
        "html-report",
        help="Generate an HTML summary report from a manifest JSON.",
    )
    html_parser.add_argument(
        "--manifest",
        type=str,
        required=True,
        help="Path to manifest JSON file",
    )
    html_parser.add_argument(
        "--output-file",
        type=str,
        help="Path to write the HTML report. Defaults to stdout",
    )
    html_parser.set_defaults(func=_handle_html_command)


def _handle_command(args: argparse.Namespace) -> None:
    with open(args.input_json, "r") as fh:
        data = json.load(fh)

    result: EncodeResult | DecodeResult
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


def _handle_html_command(args: argparse.Namespace) -> None:
    html = generate_html_report(args.manifest)
    if args.output_file:
        with open(args.output_file, "w", encoding="utf-8") as fh:
            fh.write(html)
    else:
        sys.stdout.write(html)
