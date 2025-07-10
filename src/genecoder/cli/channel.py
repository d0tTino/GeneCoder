from __future__ import annotations

"""Combine simulators and synthesis constraints into a single channel."""

import argparse
import json
import logging
import os
import random
from pathlib import Path
from typing import Sequence


from genecoder.formats import from_fasta, to_fasta
from genecoder.simulators import SIMULATOR_REGISTRY, ChannelPipeline
from genecoder.channels.base import BaseChannel
from genecoder.synthesis import SynthesisConstraints, validate_sequence
from genecoder.error_simulation import introduce_errors
from genecoder.metrics import increment as increment_metric
from .options import ChannelOptions, build_channel_options

logger = logging.getLogger(__name__)


def _load_config(path: str) -> tuple[list[str], dict[str, int]]:
    import yaml
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


def _apply_simulators(
    sequence: str,
    simulators: Sequence[str],
    *,
    parallel: bool = False,
    threads: int | None = None,
    processes: int | None = None,
    mpi: bool = False,
    mpi_workers: int | None = None,
) -> str:
    channels: list[BaseChannel] = []
    for name in simulators:
        if name not in SIMULATOR_REGISTRY:
            logger.error("Unknown simulator: %s", name)
            raise SystemExit(1)
        channels.append(SIMULATOR_REGISTRY[name])
    pipeline = ChannelPipeline(channels)
    workers = mpi_workers or processes or threads
    result: str = pipeline.simulate(
        sequence,
        parallel=parallel or mpi,
        workers=workers,
        use_process_pool=processes is not None,
        use_mpi=mpi,
    )
    for name in simulators:
        logger.info("Applied %s simulator", name)
    return result


def process_channel(
    input_file: str,
    output_file: str,
    simulators: Sequence[str],
    constraints: dict[str, int],
    *,
    sub_prob: float = 0.0,
    ins_prob: float = 0.0,
    del_prob: float = 0.0,
    seed: int | None = None,
    parallel: bool = False,
    threads: int | None = None,
    processes: int | None = None,
    mpi: bool = False,
    mpi_workers: int | None = None,
) -> None:
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            fasta_str = f.read()
    except FileNotFoundError:
        logger.error("Error: Input file %s not found.", input_file)
        raise SystemExit(1)
    records = from_fasta(fasta_str)
    if not records:
        logger.error("No FASTA records found in %s", input_file)
        raise SystemExit(1)

    synth = SynthesisConstraints(**constraints)
    processed_records: list[tuple[str, str]] = []
    for header, seq in records:
        if simulators:
            seq = _apply_simulators(
                seq,
                simulators,
                parallel=parallel,
                threads=threads,
                processes=processes,
                mpi=mpi,
                mpi_workers=mpi_workers,
            )
        else:
            rng = random.Random(seed)
            seq = introduce_errors(
                seq,
                substitution_prob=sub_prob,
                insertion_prob=ins_prob,
                deletion_prob=del_prob,
                rng=rng,
            )
            increment_metric("oligos_simulated")

        if not validate_sequence(seq, synth):
            logger.error("Sequence violates synthesis constraints")
            raise SystemExit(1)
        logger.info("Sequence satisfies synthesis constraints")
        processed_records.append((header, seq))

    fasta_out = "".join(
        to_fasta(seq, header, line_width=80) for header, seq in processed_records
    )
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f_out:
        f_out.write(fasta_out)

    total_len = sum(len(seq) for _, seq in processed_records)
    manifest = {
        "file": os.path.basename(Path(input_file).as_posix()),
        "simulators": list(simulators),
        "probabilities": {
            "sub_prob": sub_prob,
            "ins_prob": ins_prob,
            "del_prob": del_prob,
        },
        "constraints": constraints,
        "metrics": {"length": total_len},
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
    parser.add_argument("--sub-prob", type=float, default=0.0, help="Substitution probability per nucleotide")
    parser.add_argument("--ins-prob", type=float, default=0.0, help="Insertion probability after each nucleotide")
    parser.add_argument("--del-prob", type=float, default=0.0, help="Deletion probability per nucleotide")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for deterministic output")
    parser.add_argument("--min-length", type=int, default=25, help="Minimum synthesis length")
    parser.add_argument("--max-length", type=int, default=300, help="Maximum synthesis length")
    parser.add_argument("--max-homopolymer", type=int, default=4, help="Maximum homopolymer")
    parser.add_argument("--parallel", action="store_true", help="Run channel steps in parallel")
    parser.add_argument("--threads", type=int, default=None, help="Number of worker threads")
    parser.add_argument("--processes", type=int, default=None, help="Use process pool with N workers")
    parser.add_argument("--mpi", action="store_true", help="Use MPI for parallel execution")
    parser.add_argument("--mpi-workers", type=int, default=None, help="Number of MPI workers")
    parser.set_defaults(func=_handle_command)


def _handle_command(args: argparse.Namespace) -> None:
    try:
        opts: ChannelOptions = build_channel_options(args)
    except ValueError as exc:
        logger.error(str(exc))
        raise SystemExit(1)

    process_channel(
        args.input_file,
        args.output_file,
        opts.simulators,
        opts.constraints,
        sub_prob=opts.sub_prob,
        ins_prob=opts.ins_prob,
        del_prob=opts.del_prob,
        seed=opts.seed,
        parallel=opts.parallel,
        threads=opts.threads,
        processes=opts.processes,
        mpi=opts.mpi,
        mpi_workers=opts.mpi_workers,
    )
