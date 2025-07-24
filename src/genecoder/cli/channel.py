from __future__ import annotations

"""Combine simulators and synthesis constraints into a single channel."""

import argparse
import json
import logging
import os
import random
from pathlib import Path
from typing import Sequence, Dict, Any


from genecoder.formats import from_fasta, to_fasta
from genecoder.simulators import SIMULATOR_REGISTRY, ChannelPipeline
from genecoder.channel_config import ChannelConfig
from genecoder.channels.base import BaseChannel
from genecoder.synthesis import SynthesisConstraints, validate_sequence
from genecoder.error_simulation import introduce_errors
from genecoder.metrics import metrics
from genecoder.parallel import parallel_map
from .options import ChannelOptions, build_channel_options
from .shared import add_single_io_args

logger = logging.getLogger(__name__)


def _load_config(
    path: str,
) -> tuple[
    list[tuple[str, Dict[str, Any]]],
    dict[str, int],
    ChannelConfig,
    dict[str, Any],
]:
    try:
        import yaml
    except Exception:  # pragma: no cover - optional dependency
        from genecoder.plugin_manager import yaml as yaml_module
        if yaml_module is None:
            raise
        yaml = yaml_module

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:  # pragma: no cover - invalid YAML path
            raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Config file must map keys to values")

    sim_section = data.get("simulators", [])
    if not isinstance(sim_section, Sequence):
        raise ValueError("'simulators' must be a list")

    simulators: list[tuple[str, Dict[str, Any]]] = []
    for item in sim_section:
        if isinstance(item, str):
            simulators.append((item, {}))
        elif isinstance(item, dict):
            name = item.get("name")
            if not isinstance(name, str):
                raise ValueError("Simulator mapping must contain a string 'name'")
            params = {k: v for k, v in item.items() if k != "name"}
            simulators.append((name, params))
        else:
            raise ValueError("Each simulator must be a string or mapping")

    synth_section = data.get("synthesis", data.get("constraints", {}))
    if not isinstance(synth_section, dict):
        raise ValueError("'synthesis' must be a mapping")

    pipeline = data.get("pipeline", {})
    if not isinstance(pipeline, dict):
        raise ValueError("'pipeline' must be a mapping")

    cfg = ChannelConfig(
        parallel=bool(pipeline.get("parallel", False)),
        workers=pipeline.get("workers"),
        use_process_pool=bool(pipeline.get("use_process_pool", False)),
        use_mpi=bool(pipeline.get("use_mpi", False)),
        illumina_profile=pipeline.get("illumina_profile"),
        nanopore_profile=pipeline.get("nanopore_profile"),
    )

    extra = {
        "input_file": data.get("input"),
        "output_file": data.get("output"),
        "sub_prob": float(data.get("sub_prob", 0.0) or 0.0),
        "ins_prob": float(data.get("ins_prob", 0.0) or 0.0),
        "del_prob": float(data.get("del_prob", 0.0) or 0.0),
        "seed": data.get("seed"),
        "batch_workers": data.get("batch_workers"),
    }

    return simulators, {k: int(v) for k, v in synth_section.items()}, cfg, extra


def _apply_simulators(
    sequence: str,
    simulators: Sequence[tuple[str, Dict[str, Any]]],
    *,
    config: ChannelConfig,
) -> str:
    channels: list[BaseChannel] = []
    for name, params in simulators:
        if name not in SIMULATOR_REGISTRY:
            logger.error("Unknown simulator: %s", name)
            raise SystemExit(1)
        channel = SIMULATOR_REGISTRY[name]
        if params:
            try:
                channel = type(channel)(**params)
            except Exception as exc:
                logger.error("Invalid parameters for %s: %s", name, exc)
                raise SystemExit(1)
        channels.append(channel)
    pipeline = ChannelPipeline(channels)
    result: str = pipeline.simulate(sequence, config=config)
    for name, _ in simulators:
        logger.info("Applied %s simulator", name)
    return result


def process_channel(
    input_file: str,
    output_file: str,
    simulators: Sequence[tuple[str, Dict[str, Any]]],
    constraints: dict[str, int],
    *,
    sub_prob: float = 0.0,
    ins_prob: float = 0.0,
    del_prob: float = 0.0,
    seed: int | None = None,
    config: ChannelConfig | None = None,
    batch_workers: int | None = None,
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

    try:
        synth = SynthesisConstraints(**constraints)
    except ValueError:
        synth = SynthesisConstraints()
    headers = [h for h, _ in records]
    sequences = [s for _, s in records]

    def _process(item: tuple[int, str]) -> str:
        idx, seq = item
        if simulators:
            cfg = config or ChannelConfig()
            seq = _apply_simulators(seq, simulators, config=cfg)
        else:
            rng = random.Random(seed + idx if seed is not None else None)
            seq = introduce_errors(
                seq,
                substitution_prob=sub_prob,
                insertion_prob=ins_prob,
                deletion_prob=del_prob,
                rng=rng,
            )
            metrics.increment("oligos_simulated")
        if not validate_sequence(seq, synth):
            raise ValueError("Sequence violates synthesis constraints")
        logger.info("Sequence satisfies synthesis constraints")
        return seq

    if batch_workers and len(sequences) > 1:
        processed_seqs = parallel_map(
            _process,
            list(enumerate(sequences)),
            workers=batch_workers,
        )
    else:
        processed_seqs = [_process(p) for p in enumerate(sequences)]

    processed_records = list(zip(headers, processed_seqs))

    fasta_out = "".join(
        to_fasta(seq, header, line_width=80) for header, seq in processed_records
    )
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f_out:
        f_out.write(fasta_out)

    total_len = sum(len(seq) for _, seq in processed_records)
    manifest = {
        "file": os.path.basename(Path(input_file).as_posix()),
        "simulators": [name for name, _ in simulators],
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


def register_subcommand(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "channel", help="Combine simulators and synthesis constraints"
    )

    channel_sub = parser.add_subparsers(dest="channel_command")

    run_parser = channel_sub.add_parser(
        "run", help="Run channel pipeline from a YAML config"
    )
    run_parser.add_argument("config", type=str, help="Path to channel config")
    run_parser.set_defaults(func=_handle_run)

    apply_parser = channel_sub.add_parser(
        "apply", help="Apply simulators and synthesis constraints"
    )

    add_single_io_args(
        apply_parser,
        input_help="Path to input FASTA",
        output_help="Path to output FASTA",
    )

    parser.add_argument("--input-file", type=str, help="Path to input FASTA")
    parser.add_argument("--output-file", type=str, help="Path to output FASTA")

    for target in (parser, apply_parser):
        target.add_argument(
            "--simulator",
            dest="simulators",
            action="append",
            default=[],
            help="Simulator to apply (can be repeated)",
        )
        target.add_argument(
            "--config",
            type=str,
            help="YAML/JSON config defining simulators, synthesis and pipeline",
        )
        target.add_argument("--sub-prob", type=float, default=0.0, help="Substitution probability per nucleotide")
        target.add_argument("--ins-prob", type=float, default=0.0, help="Insertion probability after each nucleotide")
        target.add_argument("--del-prob", type=float, default=0.0, help="Deletion probability per nucleotide")
        target.add_argument("--illumina-depth", type=int, default=None, help="Coverage depth for Illumina reads")
        target.add_argument("--illumina-quality", type=str, default=None, help="Comma-separated quality profile or path to JSON")
        target.add_argument("--illumina-context", type=str, default=None, help="Path to JSON/YAML context error map")
        target.add_argument("--nanopore-depth", type=int, default=None, help="Coverage depth for Nanopore reads")
        target.add_argument("--nanopore-quality", type=str, default=None, help="Comma-separated quality profile or path to JSON")
        target.add_argument("--nanopore-context", type=str, default=None, help="Path to JSON/YAML context error map")
        target.add_argument("--seed", type=int, default=None, help="Random seed for deterministic output")
        target.add_argument("--min-length", type=int, default=25, help="Minimum synthesis length")
        target.add_argument("--max-length", type=int, default=300, help="Maximum synthesis length")
        target.add_argument("--max-homopolymer", type=int, default=4, help="Maximum homopolymer")
        target.add_argument(
            "--parallel",
            action="store_true",
            help="Run channel steps concurrently",
        )
        target.add_argument("--threads", type=int, default=None, help="Number of worker threads")
        target.add_argument("--processes", type=int, default=None, help="Use process pool with N workers")
        target.add_argument(
            "--batch-workers",
            type=int,
            default=None,
            help="Process sequences in parallel using N workers",
        )
        target.set_defaults(func=_handle_command)

    parser.set_defaults(channel_command="apply")


def _handle_command(args: argparse.Namespace) -> None:
    run_channel(args)


def run_channel(args: argparse.Namespace) -> None:
    """Run the channel command using ``args``."""

    try:
        opts: ChannelOptions = build_channel_options(args)
    except ValueError as exc:
        logger.error(str(exc))
        raise SystemExit(1)

    cfg = ChannelConfig(
        parallel=opts.parallel,
        workers=opts.processes or opts.threads,
        use_process_pool=opts.processes is not None,
        use_mpi=False,
        illumina_profile=None,
        nanopore_profile=None,
    )
    simulators = opts.simulator_specs
    if simulators is None:
        simulators = [(name, {}) for name in opts.simulators]

    updated: list[tuple[str, dict[str, object]]] = []
    for name, params in simulators:
        new_params = dict(params)
        if name.startswith("illumina"):
            if opts.illumina_depth is not None:
                new_params.setdefault("coverage", opts.illumina_depth)
            if opts.illumina_quality is not None:
                new_params.setdefault("quality_profile", opts.illumina_quality)
            if opts.illumina_context is not None:
                new_params.setdefault("context_errors", opts.illumina_context)
        if name.startswith("nanopore"):
            if opts.nanopore_depth is not None:
                new_params.setdefault("coverage", opts.nanopore_depth)
            if opts.nanopore_quality is not None:
                new_params.setdefault("quality_profile", opts.nanopore_quality)
            if opts.nanopore_context is not None:
                new_params.setdefault("context_errors", opts.nanopore_context)
        updated.append((name, new_params))
    simulators = updated

    process_channel(
        args.input_file,
        args.output_file,
        simulators,
        opts.constraints,
        sub_prob=opts.sub_prob,
        ins_prob=opts.ins_prob,
        del_prob=opts.del_prob,
        seed=opts.seed,
        config=cfg,
        batch_workers=opts.batch_workers,
    )


def _handle_run(args: argparse.Namespace) -> None:
    try:
        simulators, constraints, cfg, extra = _load_config(args.config)
    except Exception as exc:  # pragma: no cover - config error handling
        logger.error(str(exc))
        raise SystemExit(1)

    input_file = extra.get("input_file")
    output_file = extra.get("output_file")
    if not input_file or not output_file:
        logger.error("Config must define 'input' and 'output' paths")
        raise SystemExit(1)

    process_channel(
        input_file,
        output_file,
        simulators,
        constraints,
        sub_prob=extra.get("sub_prob", 0.0),
        ins_prob=extra.get("ins_prob", 0.0),
        del_prob=extra.get("del_prob", 0.0),
        seed=extra.get("seed"),
        config=cfg,
        batch_workers=extra.get("batch_workers"),
    )
