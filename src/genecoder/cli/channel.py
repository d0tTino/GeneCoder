from __future__ import annotations

"""Combine simulators and synthesis constraints into a single channel."""

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Sequence

import yaml

from genecoder.formats import from_fasta, to_fasta
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.synthesis import SynthesisConstraints, validate_sequence

logger = logging.getLogger(__name__)


def _load_config(path: str) -> tuple[list[str], dict[str, int]]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("Config file must map keys to values")
    sim = data.get("simulators", [])
    if not isinstance(sim, Sequence):
        raise ValueError("'simulators' must be a list")
    constraints = data.get("constraints", {})
    if not isinstance(constraints, dict):
        raise ValueError("'constraints' must be a mapping")
    return list(sim), {k: int(v) for k, v in constraints.items()}


def _apply_simulators(sequence: str, simulators: Sequence[str]) -> str:
    for name in simulators:
        if name not in SIMULATOR_REGISTRY:
            logger.error("Unknown simulator: %s", name)
            raise SystemExit(1)
        channel = SIMULATOR_REGISTRY[name]
        sequence = channel.simulate(sequence)
        logger.info("Applied %s simulator", name)
    return sequence


def process_channel(
    input_file: str,
    output_file: str,
    simulators: Sequence[str],
    constraints: dict[str, int],
) -> None:
    with open(input_file, "r", encoding="utf-8") as f:
        fasta_str = f.read()
    records = from_fasta(fasta_str)
    if not records:
        logger.error("No FASTA records found in %s", input_file)
        raise SystemExit(1)
    header, seq = records[0]

    seq = _apply_simulators(seq, simulators)

    synth = SynthesisConstraints(**constraints)
    if not validate_sequence(seq, synth):
        logger.error("Sequence violates synthesis constraints")
        raise SystemExit(1)
    logger.info("Sequence satisfies synthesis constraints")

    fasta_out = to_fasta(seq, header, line_width=80)
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f_out:
        f_out.write(fasta_out)

    manifest = {
        "file": os.path.basename(Path(input_file).as_posix()),
        "simulators": list(simulators),
        "constraints": constraints,
        "metrics": {"length": len(seq)},
    }
    manifest_path = os.path.splitext(output_file)[0] + ".manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as m_out:
        json.dump(manifest, m_out, indent=2)
    logger.info("Manifest written to %s", manifest_path)


def register_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("channel", help="Combine simulators and synthesis constraints")
    parser.add_argument("--input-file", required=True, type=str, help="Path to input FASTA")
    parser.add_argument("--output-file", required=True, type=str, help="Path to output FASTA")
    parser.add_argument(
        "--simulator",
        dest="simulators",
        action="append",
        default=[],
        help="Simulator to apply (can be repeated)",
    )
    parser.add_argument("--config", type=str, help="YAML config defining simulators and constraints")
    parser.add_argument("--min-length", type=int, default=25, help="Minimum synthesis length")
    parser.add_argument("--max-length", type=int, default=300, help="Maximum synthesis length")
    parser.add_argument("--max-homopolymer", type=int, default=4, help="Maximum homopolymer")
    parser.set_defaults(func=_handle_command)


def _handle_command(args: argparse.Namespace) -> None:
    simulators = list(args.simulators)
    constraints = {
        "min_length": args.min_length,
        "max_length": args.max_length,
        "max_homopolymer": args.max_homopolymer,
    }
    if args.config:
        cfg_sim, cfg_con = _load_config(args.config)
        if cfg_sim:
            simulators = cfg_sim
        constraints.update(cfg_con)
    if not simulators:
        logger.error("At least one simulator must be specified")
        raise SystemExit(1)
    process_channel(args.input_file, args.output_file, simulators, constraints)
