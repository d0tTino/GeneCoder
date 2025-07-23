"""Helper functions and dataclasses for CLI argument handling."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import List, Dict, Sequence

from genecoder.options import EncodingOptions, DecodingOptions


@dataclass
class ChannelOptions:
    """Options for the ``channel`` subcommand."""

    simulators: List[str]
    constraints: Dict[str, int]
    sub_prob: float = 0.0
    ins_prob: float = 0.0
    del_prob: float = 0.0
    seed: int | None = None
    parallel: bool = False
    threads: int | None = None
    processes: int | None = None
    batch_workers: int | None = None
    simulator_specs: list[tuple[str, dict[str, object]]] | None = None
    illumina_depth: int | None = None
    nanopore_depth: int | None = None
    illumina_quality: Sequence[float] | None = None
    nanopore_quality: Sequence[float] | None = None
    illumina_context: Dict[str, float] | None = None
    nanopore_context: Dict[str, float] | None = None


def _parse_quality(value: str | None) -> Sequence[float] | None:
    if value is None:
        return None
    from pathlib import Path
    try:
        path = Path(value)
        if path.is_file():
            import json
            import yaml
            text = path.read_text(encoding="utf-8")
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = yaml.safe_load(text)
            if isinstance(data, Sequence):
                return [float(x) for x in data]
            raise ValueError("quality profile must be a list")
    except Exception:
        pass
    return [float(x) for x in value.split(",") if x]


def _parse_context(value: str | None) -> Dict[str, float] | None:
    if value is None:
        return None
    from pathlib import Path
    path = Path(value)
    if not path.is_file():
        raise ValueError("context file not found")
    import json
    import yaml
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("context must be a mapping")
    return {str(k).upper(): float(v) for k, v in data.items()}


def _validate_simulator_prob_args(
    simulators: Sequence[str], sub_prob: float, ins_prob: float, del_prob: float
) -> None:
    """Ensure that simulator and probability arguments are valid."""

    prob_specified = any([sub_prob, ins_prob, del_prob])
    if simulators and prob_specified:
        raise ValueError(
            "Probability options cannot be combined with --simulator or --config"
        )
    if not simulators and not prob_specified:
        raise ValueError(
            "At least one simulator or probability option must be specified"
        )


def build_encoding_options(args: argparse.Namespace) -> EncodingOptions:
    """Create :class:`EncodingOptions` from parsed CLI arguments."""

    if not 0 <= args.gc_min <= 1 or not 0 <= args.gc_max <= 1:
        raise ValueError("gc_min and gc_max must be between 0 and 1")
    if args.gc_min > args.gc_max:
        raise ValueError("gc_min cannot be greater than gc_max")

    return EncodingOptions(
        method=args.method,
        add_parity=args.add_parity,
        k_value=args.k_value,
        parity_rule=args.parity_rule,
        fec=args.fec,
        gc_min=args.gc_min,
        gc_max=args.gc_max,
        max_homopolymer=args.max_homopolymer,
        alphabet=getattr(args, "alphabet", "base4"),
    )


def build_decoding_options(args: argparse.Namespace) -> DecodingOptions:
    """Create :class:`DecodingOptions` from parsed CLI arguments."""

    return DecodingOptions(
        method=args.method,
        check_parity=args.check_parity,
        k_value=args.k_value,
        parity_rule=args.parity_rule,
        alphabet=getattr(args, "alphabet", "base4"),
    )


def build_channel_options(args: argparse.Namespace) -> ChannelOptions:
    """Create :class:`ChannelOptions` from parsed CLI arguments."""

    from .channel import _load_config  # Local import to avoid heavy deps at import time

    simulators = list(args.simulators)
    constraints = {
        "min_length": args.min_length,
        "max_length": args.max_length,
        "max_homopolymer": args.max_homopolymer,
    }

    sim_specs: list[tuple[str, dict[str, object]]] | None = None
    if args.config:
        cfg_sim, cfg_con, cfg_pipeline, _ = _load_config(args.config)
        if cfg_sim:
            sim_specs = cfg_sim
            simulators = [name for name, _ in cfg_sim]
        constraints.update(cfg_con)
        if not args.parallel and cfg_pipeline.parallel:
            args.parallel = True
        if args.threads is None and args.processes is None:
            if cfg_pipeline.workers is not None:
                args.threads = cfg_pipeline.workers
        if cfg_pipeline.use_process_pool:
            args.processes = args.threads

    _validate_simulator_prob_args(
        simulators, args.sub_prob, args.ins_prob, args.del_prob
    )
    if args.min_length <= 0:
        raise ValueError("min_length must be greater than 0")
    if args.max_length <= 0:
        raise ValueError("max_length must be greater than 0")
    if args.min_length > args.max_length:
        raise ValueError("min_length cannot be greater than max_length")
    if args.threads is not None and args.processes is not None:
        raise ValueError("Cannot specify both --threads and --processes")
    if args.batch_workers is not None and args.batch_workers <= 0:
        raise ValueError("batch_workers must be greater than 0")

    return ChannelOptions(
        simulators=simulators,
        constraints=constraints,
        sub_prob=args.sub_prob,
        ins_prob=args.ins_prob,
        del_prob=args.del_prob,
        seed=args.seed,
        parallel=args.parallel,
        threads=args.threads,
        processes=args.processes,
        batch_workers=args.batch_workers,
        simulator_specs=sim_specs,
        illumina_depth=args.illumina_depth,
        nanopore_depth=args.nanopore_depth,
        illumina_quality=_parse_quality(args.illumina_quality),
        nanopore_quality=_parse_quality(args.nanopore_quality),
        illumina_context=_parse_context(args.illumina_context),
        nanopore_context=_parse_context(args.nanopore_context),
    )
