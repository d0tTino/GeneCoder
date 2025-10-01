from __future__ import annotations

"""CLI helpers for the core encode/ECC/channel/decode pipeline."""

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

from genecoder.simulators.illumina import ILLUMINA_PROFILES
from genecoder.simulators.nanopore import NANOPORE_PROFILES

from genecoder.core import encode, simulate, decode, metrics as gather_metrics
from genecoder.html_report import generate_html_report
from genecoder.manifest import generate_manifest
from genecoder.parallel import parallel_map
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
) -> Dict[str, Any]:
    """Run pipeline with optional ``channel_params`` and return metrics."""

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

    chan_name = channel or "none"
    temp_name = chan_name
    if chan_name != "none":
        ch = SIMULATOR_REGISTRY[chan_name]
        if channel_params:
            try:
                ch = type(ch)(**channel_params)
            except Exception as exc:
                logger.error("Invalid channel parameters for %s: %s", chan_name, exc)
                raise SystemExit(1)
        temp_name = f"_tmp_{chan_name}"
        SIMULATOR_REGISTRY[temp_name] = ch
    try:
        original_data = Path(input_path).read_bytes()
        dna, fec_info = encode(codec, fec, original_data)
        dna, subs, ins, dels, coverage = simulate(temp_name, dna)
        decoded = decode(codec, fec, dna, fec_info)
        Path(output_path).write_bytes(decoded)
        metrics: dict[str, Any] = gather_metrics(

            dna,
            original_data,
            decoded,
            fec,
            subs,
            ins,
            dels,
            coverage,
        )
    finally:
        if temp_name != chan_name and temp_name in SIMULATOR_REGISTRY:
            del SIMULATOR_REGISTRY[temp_name]
    return metrics



def register_subcommand(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "pipeline", help="Run encode->FEC->channel->decode pipeline"
    )
    codec_choices = sorted(CODEC_REGISTRY.keys()) or None
    fec_choices = sorted(FEC_REGISTRY.keys())
    chan_choices = ["none", *sorted(SIMULATOR_REGISTRY.keys())]
    illumina_profiles = ", ".join(sorted(ILLUMINA_PROFILES))
    nanopore_profiles = ", ".join(sorted(NANOPORE_PROFILES))

    parser.add_argument("input", help="Path to input file")
    parser.add_argument("output", help="Path to output file")

    parser.add_argument("-c", "--config", help="YAML configuration file")

    parser.add_argument("--codec", choices=codec_choices, default=None)
    if fec_choices:
        parser.add_argument("--fec", choices=fec_choices, default=None)
    else:
        parser.add_argument("--fec", default=None)
    parser.add_argument(
        "--channel",
        choices=chan_choices,
        default=None,
        help=(
            "Channel simulator to apply. Illumina profiles: "
            f"{illumina_profiles}. Nanopore profiles: {nanopore_profiles}."
        ),
    )
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
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for random components to ensure reproducible runs.",
    )
    parser.add_argument(
        "--mpi-workers",
        type=int,
        default=None,
        help="Distribute encoding tasks across MPI workers",
    )

    parser.set_defaults(func=_handle_command)


def _handle_command(args: argparse.Namespace) -> None:
    if args.seed is not None:
        os.environ["GENECODER_SIM_SEED"] = str(args.seed)
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
                channel_params["substitution_prob"] = args.sub_rate
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

    def _execute() -> Dict[str, Any]:
        return _run_with_params(
            codec, fec, channel, channel_params, args.input, args.output
        )

    if args.mpi_workers:
        metrics = parallel_map(
            lambda _: _execute(),
            [None],
            workers=args.mpi_workers,
            use_mpi=True,
        )[0]
    else:
        metrics = _execute()

    metrics_path = Path(str(args.output) + ".json")
    metrics_path.write_text(json.dumps({"metrics": metrics}))
    logger.info("Metrics written to %s", metrics_path)

    manifest_params: Dict[str, Any] = {"method": codec}
    if fec:
        manifest_params["fec"] = fec
    if channel and channel != "none":
        manifest_params["channel"] = channel
        if channel_params:
            manifest_params["channel_parameters"] = channel_params

    manifest = generate_manifest(args.input, manifest_params, metrics)
    manifest_path = metrics_path.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info("Manifest written to %s", manifest_path)

    html_report_path = metrics_path.with_suffix(".html")
    html = generate_html_report(str(manifest_path))
    html_report_path.write_text(html, encoding="utf-8")
    logger.info("HTML report written to %s", html_report_path)
