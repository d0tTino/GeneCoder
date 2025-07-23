from __future__ import annotations

"""CLI helpers for the core encode/ECC/channel/decode pipeline."""

import argparse
import logging

from genecoder.core import run_pipeline
from genecoder.plugin_manager import CODEC_REGISTRY, FEC_REGISTRY
from genecoder.simulators import SIMULATOR_REGISTRY

logger = logging.getLogger(__name__)


def register_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "pipeline", help="Run encode->FEC->channel->decode pipeline"
    )
    codec_choices = sorted(CODEC_REGISTRY.keys()) or None
    fec_choices = sorted(FEC_REGISTRY.keys())
    chan_choices = ["none", *sorted(SIMULATOR_REGISTRY.keys())]
    parser.add_argument("input", help="Path to input file")
    parser.add_argument("output", help="Path to output file")
    parser.add_argument("--codec", required=True, choices=codec_choices)
    if fec_choices:
        parser.add_argument("--fec", choices=fec_choices, default=None)
    else:
        parser.add_argument("--fec", default=None)
    parser.add_argument("--channel", choices=chan_choices, default="none")
    parser.set_defaults(func=_handle_command)


def _handle_command(args: argparse.Namespace) -> None:
    run_pipeline(args.codec, args.fec, args.channel, args.input, args.output)
