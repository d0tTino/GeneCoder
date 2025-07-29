from __future__ import annotations

"""CLI helpers for the core encode/ECC/channel/decode pipeline."""

import argparse
import logging
from pathlib import Path
from typing import Any, Dict

from genecoder.core import run_pipeline
from genecoder.plugin_manager import (
    CODEC_REGISTRY,
    FEC_REGISTRY,
    yaml as yaml_module,
    init_plugins,
)
from genecoder.simulators import SIMULATOR_REGISTRY

logger = logging.getLogger(__name__)


def _load_config(path: str) -> tuple[str, str | None, str | None, Dict[str, Any]]:
    """Parse pipeline settings from a YAML ``path``."""

    if yaml_module is None:  # pragma: no cover - optional dependency
        import yaml as yaml_fallback
    else:
        yaml_fallback = yaml_module

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = yaml_fallback.safe_load(f) or {}
        except Exception as exc:  # pragma: no cover - invalid YAML path
            raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Config file must map keys to values")

    codec = data.get("codec")
    if not isinstance(codec, str):
        raise ValueError("'codec' must be a string")

    fec = data.get("fec")
    if fec is not None and not isinstance(fec, str):
        raise ValueError("'fec' must be a string")

    channel_info = data.get("channel")
    channel = None
    channel_params: Dict[str, Any] = {}
    if isinstance(channel_info, str):
        channel = channel_info
    elif isinstance(channel_info, dict):
        channel = channel_info.get("name")
        if not isinstance(channel, str):
            raise ValueError("'channel' mapping must contain a string 'name'")
        channel_params = {k: v for k, v in channel_info.items() if k != "name"}
    elif channel_info is not None:
        raise ValueError("'channel' must be a string or mapping")

    return codec, fec, channel, channel_params


def _run_with_params(
    codec: str,
    fec: str | None,
    channel: str | None,
    channel_params: Dict[str, Any],
    input_path: str,
    output_path: str,
) -> None:
    """Run pipeline with optional ``channel_params``."""

    init_plugins()

    if codec not in CODEC_REGISTRY:
        logger.error("Unknown codec: %s", codec)
        raise SystemExit(1)
    if fec and fec not in FEC_REGISTRY:
        logger.error("Unknown FEC: %s", fec)
        raise SystemExit(1)
    if channel and channel != "none" and channel not in SIMULATOR_REGISTRY:
        logger.error("Unknown channel: %s", channel)
        raise SystemExit(1)

    data = Path(input_path).read_bytes()

    fec_info: Any | None = None
    if fec:
        data, fec_info = FEC_REGISTRY[fec]["encode"](data)

    dna = CODEC_REGISTRY[codec]["encode"](data)

    if channel and channel != "none":
        ch = SIMULATOR_REGISTRY[channel]
        if channel_params:
            try:
                ch = type(ch)(**channel_params)
            except Exception as exc:
                logger.error("Invalid channel parameters for %s: %s", channel, exc)
                raise SystemExit(1)
        dna = ch.simulate(dna)

    decoded_any = CODEC_REGISTRY[codec]["decode"](dna)
    assert isinstance(decoded_any, (bytes, bytearray))
    decoded = bytes(decoded_any)

    if fec:
        assert fec_info is not None
        decoded, _ = FEC_REGISTRY[fec]["decode"](decoded, fec_info)

    Path(output_path).write_bytes(decoded)


def register_subcommand(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "pipeline", help="Run encode->FEC->channel->decode pipeline"
    )
    codec_choices = sorted(CODEC_REGISTRY.keys()) or None
    fec_choices = sorted(FEC_REGISTRY.keys())
    chan_choices = ["none", *sorted(SIMULATOR_REGISTRY.keys())]

    parser.add_argument("input", help="Path to input file")
    parser.add_argument("output", help="Path to output file")

    parser.add_argument("--config", help="YAML configuration file")

    parser.add_argument("--codec", choices=codec_choices, default=None)
    if fec_choices:
        parser.add_argument("--fec", choices=fec_choices, default=None)
    else:
        parser.add_argument("--fec", default=None)
    parser.add_argument("--channel", choices=chan_choices, default=None)
    parser.add_argument(
        "--sub-rate",
        type=float,
        default=None,
        help="Substitution rate/probability for the selected channel",
    )
    parser.add_argument(
        "--ins-rate",
        type=float,
        default=None,
        help="Insertion rate/probability for the selected channel",
    )
    parser.add_argument(
        "--del-rate",
        type=float,
        default=None,
        help="Deletion rate/probability for the selected channel",
    )

    parser.set_defaults(func=_handle_command)


def _handle_command(args: argparse.Namespace) -> None:
    cfg_codec = cfg_fec = cfg_channel = None
    cfg_params: Dict[str, Any] = {}

    if args.config:
        cfg_codec, cfg_fec, cfg_channel, cfg_params = _load_config(args.config)

    codec = args.codec or cfg_codec
    fec = args.fec if args.fec is not None else cfg_fec
    channel = args.channel or cfg_channel
    channel_params = cfg_params if channel == cfg_channel else {}
    if channel is not None and channel != "none":
        if args.sub_rate is not None:
            if channel == "indel":
                channel_params["substitution_prob"] = args.sub_rate
            elif channel != "simple":
                channel_params["substitution_rate"] = args.sub_rate
            else:
                channel_params["error_rate"] = args.sub_rate
        if args.ins_rate is not None:
            if channel == "indel":
                channel_params["insertion_prob"] = args.ins_rate
            elif channel != "simple":
                channel_params["insertion_rate"] = args.ins_rate
        if args.del_rate is not None:
            if channel == "indel":
                channel_params["deletion_prob"] = args.del_rate
            elif channel != "simple":
                channel_params["deletion_rate"] = args.del_rate

    if codec is None:
        logger.error("Codec must be specified via --codec or config")
        raise SystemExit(1)

    if channel is None:
        channel = "none"

    if channel_params:
        _run_with_params(codec, fec, channel, channel_params, args.input, args.output)
    else:
        run_pipeline(codec, fec, channel, args.input, args.output)
