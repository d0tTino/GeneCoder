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
    coverage: int | None = None
    quality_profile: Sequence[float] | None = None
    illumina_depth: int | None = None
    nanopore_depth: int | None = None
    illumina_quality: Sequence[float] | None = None
    nanopore_quality: Sequence[float] | None = None
    illumina_context: Dict[str, float] | None = None
    nanopore_context: Dict[str, float] | None = None
    illumina_sub_rate: float | None = None
    illumina_ins_rate: float | None = None
    illumina_del_rate: float | None = None
    nanopore_sub_rate: float | None = None
    nanopore_ins_rate: float | None = None
    nanopore_del_rate: float | None = None
    profile: str | None = None
    illumina_profile: str | None = None
    nanopore_profile: str | None = None
    dnarsim_profile: str | None = None
    indel_profile: str | None = None
    nanopore_profile_file: str | None = None
    sub_rate: float | None = None
    ins_rate: float | None = None
    del_rate: float | None = None
    decay_rate: float | None = None
    dropout_rate: float | None = None
    coverage_distribution: Dict[int, float] | None = None
    synthesis_loss: float | None = None


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


def _parse_distribution(value: str | None) -> Dict[int, float] | None:
    if value is None:
        return None
    from pathlib import Path
    path = Path(value)
    data: object
    if path.is_file():
        import json
        import yaml

        text = path.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = yaml.safe_load(text)
    else:
        data = value

    if isinstance(data, dict):
        result: Dict[int, float] = {}
        for key, weight in data.items():
            try:
                cov = int(key)
                wt = float(weight)
            except (TypeError, ValueError):
                continue
            if wt < 0:
                continue
            result[cov] = result.get(cov, 0.0) + wt
        return result or None

    if isinstance(data, Sequence) and not isinstance(data, str):
        result: Dict[int, float] = {}
        for item in data:
            try:
                cov = int(item)
            except (TypeError, ValueError):
                continue
            result[cov] = result.get(cov, 0.0) + 1.0
        return result or None

    if isinstance(data, str):
        result: Dict[int, float] = {}
        for chunk in data.split(","):
            if not chunk:
                continue
            if ":" in chunk:
                key, weight = chunk.split(":", 1)
            else:
                key, weight = chunk, "1"
            try:
                cov = int(key.strip())
                wt = float(weight.strip())
            except ValueError:
                continue
            if wt < 0:
                continue
            result[cov] = result.get(cov, 0.0) + wt
        return result or None

    raise ValueError("coverage distribution must be a mapping or sequence")


def _validate_simulator_prob_args(
    simulators: Sequence[str],
    sub_prob: float,
    ins_prob: float,
    del_prob: float,
    profile: str | None,
) -> None:
    """Ensure that simulator, profile and probability arguments are valid."""

    prob_specified = any([sub_prob, ins_prob, del_prob])
    if (simulators or profile) and prob_specified:
        raise ValueError(
            "Probability options cannot be combined with --simulator, --profile or --config"
        )
    if not simulators and not prob_specified and profile is None:
        raise ValueError(
            "At least one simulator, profile or probability option must be specified"
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
        seed=getattr(args, "seed", None),
        rs_symbol_size=getattr(args, "rs_symbol_size", None),
        rs_primitive=getattr(args, "rs_primitive", None),
    )


def build_decoding_options(args: argparse.Namespace) -> DecodingOptions:
    """Create :class:`DecodingOptions` from parsed CLI arguments."""

    return DecodingOptions(
        method=args.method,
        check_parity=args.check_parity,
        k_value=args.k_value,
        parity_rule=args.parity_rule,
        alphabet=getattr(args, "alphabet", "base4"),
        seed=getattr(args, "seed", None),
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
    dropout_rate = getattr(args, "dropout_rate", None)
    synthesis_loss = getattr(args, "synthesis_loss", None)
    coverage_distribution = _parse_distribution(
        getattr(args, "coverage_distribution", None)
    )

    if args.config:
        cfg_sim, cfg_con, cfg_pipeline, extra = _load_config(args.config)
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
        if getattr(args, "decay_rate", None) is None:
            args.decay_rate = extra.get("decay_rate")
        if dropout_rate is None and cfg_pipeline.dropout_rate is not None:
            dropout_rate = cfg_pipeline.dropout_rate
        if synthesis_loss is None and cfg_pipeline.synthesis_loss is not None:
            synthesis_loss = cfg_pipeline.synthesis_loss
        if coverage_distribution is None and cfg_pipeline.coverage_distribution:
            coverage_distribution = dict(cfg_pipeline.coverage_distribution)

    _validate_simulator_prob_args(
        simulators, args.sub_prob, args.ins_prob, args.del_prob, getattr(args, "profile", None)
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
    if coverage_distribution is not None:
        coverage_distribution = dict(coverage_distribution)
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
        coverage=args.coverage,
        quality_profile=_parse_quality(args.quality_profile),
        illumina_depth=args.illumina_depth,
        nanopore_depth=args.nanopore_depth,
        illumina_quality=_parse_quality(args.illumina_quality),
        nanopore_quality=_parse_quality(args.nanopore_quality),
        illumina_context=_parse_context(args.illumina_context),
        nanopore_context=_parse_context(args.nanopore_context),
        illumina_sub_rate=args.illumina_sub_rate,
        illumina_ins_rate=args.illumina_ins_rate,
        illumina_del_rate=args.illumina_del_rate,
        nanopore_sub_rate=args.nanopore_sub_rate,
        nanopore_ins_rate=args.nanopore_ins_rate,
        nanopore_del_rate=args.nanopore_del_rate,
        profile=getattr(args, "profile", None),
        illumina_profile=args.illumina_profile,
        nanopore_profile=args.nanopore_profile,
        dnarsim_profile=getattr(args, "dnarsim_profile", None),
        indel_profile=getattr(args, "indel_profile", None),
        nanopore_profile_file=args.nanopore_profile_file,
        sub_rate=args.sub_rate,
        ins_rate=args.ins_rate,
        del_rate=args.del_rate,
        decay_rate=getattr(args, "decay_rate", None),
        dropout_rate=dropout_rate,
        coverage_distribution=coverage_distribution,
        synthesis_loss=synthesis_loss,
    )
