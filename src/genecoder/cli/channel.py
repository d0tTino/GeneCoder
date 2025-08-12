from __future__ import annotations

"""Combine simulators and synthesis constraints into a single channel."""

import argparse
import json
import logging
import os
import random
from pathlib import Path
from typing import Sequence, Dict, Any
from difflib import SequenceMatcher


from genecoder.formats import from_fasta, to_fasta
from genecoder.simulators import SIMULATOR_REGISTRY, ChannelPipeline
from genecoder.channel_config import ChannelConfig
from genecoder.channels.base import BaseChannel
from genecoder.synthesis import SynthesisConstraints, validate_sequence
from genecoder.error_simulation import introduce_errors
from genecoder.metrics import metrics
from genecoder.parallel import parallel_map
from genecoder.simulators.illumina import ILLUMINA_PROFILES
from genecoder.simulators.nanopore import NANOPORE_PROFILES
from genecoder.error_simulation import INDEL_PROFILES
from genecoder.simulators.decay import DegradationChannel
from .options import ChannelOptions, build_channel_options
from .shared import add_single_io_args

logger = logging.getLogger(__name__)


PROFILE_MAP: dict[str, tuple[str, str]] = {
    "miseq": ("illumina", "miseq"),
    "hiseq": ("illumina", "hiseq"),
    "novaseq": ("illumina", "novaseq"),
    "nova": ("illumina", "nova"),
    "minion": ("nanopore", "minion"),
    "promethion": ("nanopore", "promethion"),
}


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
    if "decay_rate" in data:
        extra["decay_rate"] = float(data["decay_rate"])

    return simulators, {k: int(v) for k, v in synth_section.items()}, cfg, extra


def _load_profile_file(path: str) -> Dict[str, Any]:
    """Return parameters from YAML ``path``."""
    try:
        import yaml
    except Exception:  # pragma: no cover - optional dependency
        from genecoder.plugin_manager import yaml as yaml_module
        if yaml_module is None:
            raise
        yaml = yaml_module

    with open(path, "r", encoding="utf-8") as fh:
        try:
            data = yaml.safe_load(fh) or {}
        except Exception as exc:  # pragma: no cover - invalid YAML path
            raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Profile file must map keys to values")
    return data


def _apply_simulators(
    sequence: str,
    simulators: Sequence[
        BaseChannel | tuple[str, Dict[str, Any]]
    ],
    *,
    config: ChannelConfig,
) -> str:
    channels: list[BaseChannel] = []
    for item in simulators:
        if isinstance(item, BaseChannel):
            channel = item
            name = channel.__class__.__name__
        else:
            name, params = item
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
        logger.info("Applied %s simulator", name)
    pipeline = ChannelPipeline(channels)
    result: str = pipeline.simulate(sequence, config=config)
    return result


def _count_errors(original: str, mutated: str) -> tuple[int, int, int]:
    """Return substitution, insertion and deletion counts."""
    subs = ins = dels = 0
    sm = SequenceMatcher(None, original, mutated)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace":
            subs += max(i2 - i1, j2 - j1)
        elif tag == "delete":
            dels += i2 - i1
        elif tag == "insert":
            ins += j2 - j1
    return subs, ins, dels


def process_channel(
    input_file: str,
    output_file: str,
    simulators: Sequence[BaseChannel | tuple[str, Dict[str, Any]]],
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

    def _process(item: tuple[int, str]) -> tuple[str, tuple[int, int, int]]:
        idx, seq = item
        original = seq
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
        return seq, _count_errors(original, seq)

    if batch_workers and len(sequences) > 1:
        processed = parallel_map(
            _process,
            list(enumerate(sequences)),
            workers=batch_workers,
        )
    else:
        processed = [_process(p) for p in enumerate(sequences)]

    processed_records: list[tuple[str, str]] = []
    sub_total = ins_total = del_total = 0
    for header, (seq, stats) in zip(headers, processed):
        s, i, d = stats
        sub_total += s
        ins_total += i
        del_total += d
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
        "simulators": [name for name, _ in simulators],
        "probabilities": {
            "sub_prob": sub_prob,
            "ins_prob": ins_prob,
            "del_prob": del_prob,
        },
        "constraints": constraints,
        "metrics": {
            "length": total_len,
            "substitutions": sub_total,
            "insertions": ins_total,
            "deletions": del_total,
        },
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
    illumina_profiles = ", ".join(sorted(ILLUMINA_PROFILES))
    nanopore_profiles = ", ".join(sorted(NANOPORE_PROFILES))
    profile_names = ", ".join(sorted(PROFILE_MAP))
    run_parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_MAP),
        default=None,
        help=f"Named sequencing profile to use. Available profiles: {profile_names}",
    )
    run_parser.add_argument(
        "--illumina-profile",
        type=str,
        default=None,
        help=f"Named Illumina profile to use. Available profiles: {illumina_profiles}",
    )
    run_parser.add_argument(
        "--illumina-profile-file",
        type=str,
        default=None,
        help="YAML file with Illumina simulator parameters",
    )
    run_parser.add_argument(
        "--nanopore-profile",
        type=str,
        default=None,
        help=f"Named Nanopore profile to use. Available profiles: {nanopore_profiles}",
    )
    run_parser.add_argument(
        "--nanopore-profile-file",
        type=str,
        default=None,
        help="YAML file with Nanopore simulator parameters",
    )
    run_parser.add_argument(
        "--decay-rate",
        type=float,
        default=None,
        help="Probability of strand loss and damage",
    )
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
        target.add_argument(
            "--profile",
            choices=sorted(PROFILE_MAP),
            default=None,
            help="Named sequencing profile to use",
        )
        target.add_argument("--sub-prob", type=float, default=0.0, help="Substitution probability per nucleotide")
        target.add_argument("--ins-prob", type=float, default=0.0, help="Insertion probability after each nucleotide")
        target.add_argument("--del-prob", type=float, default=0.0, help="Deletion probability per nucleotide")
        target.add_argument(
            "--sub-rate",
            type=float,
            default=None,
            help="Substitution rate for generic simulators",
        )
        target.add_argument(
            "--ins-rate",
            type=float,
            default=None,
            help="Insertion rate for generic simulators",
        )
        target.add_argument(
            "--del-rate",
            type=float,
            default=None,
            help="Deletion rate for generic simulators",
        )
        target.add_argument(
            "--coverage",
            type=int,
            default=None,
            help="Coverage depth for simulators",
        )
        target.add_argument(
            "--quality-profile",
            type=str,
            default=None,
            help="Comma-separated quality profile or path to JSON",
        )
        target.add_argument("--illumina-depth", type=int, default=None, help="Coverage depth for Illumina reads")
        target.add_argument("--illumina-quality", type=str, default=None, help="Comma-separated quality profile or path to JSON")
        target.add_argument("--illumina-context", type=str, default=None, help="Path to JSON/YAML context error map")
        target.add_argument("--illumina-sub-rate", type=float, default=None, help="Substitution rate for Illumina reads")
        target.add_argument("--illumina-ins-rate", type=float, default=None, help="Insertion rate for Illumina reads")
        target.add_argument("--illumina-del-rate", type=float, default=None, help="Deletion rate for Illumina reads")
        target.add_argument("--illumina-profile", type=str, default=None, help="Named Illumina profile to use")
        target.add_argument("--illumina-profile-file", type=str, default=None, help="YAML file with Illumina simulator parameters")
        target.add_argument("--nanopore-depth", type=int, default=None, help="Coverage depth for Nanopore reads")
        target.add_argument("--nanopore-quality", type=str, default=None, help="Comma-separated quality profile or path to JSON")
        target.add_argument("--nanopore-context", type=str, default=None, help="Path to JSON/YAML context error map")
        target.add_argument("--nanopore-sub-rate", type=float, default=None, help="Substitution rate for Nanopore reads")
        target.add_argument("--nanopore-ins-rate", type=float, default=None, help="Insertion rate for Nanopore reads")
        target.add_argument("--nanopore-del-rate", type=float, default=None, help="Deletion rate for Nanopore reads")
        target.add_argument("--nanopore-profile", type=str, default=None, help="Named Nanopore profile to use")
        target.add_argument("--nanopore-profile-file", type=str, default=None, help="YAML file with Nanopore simulator parameters")
        target.add_argument("--indel-profile", type=str, default=None, help="Named indel profile to use")
        target.add_argument(
            "--decay-rate",
            type=float,
            default=None,
            help="Probability of strand loss and damage",
        )
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
        illumina_profile=opts.illumina_profile,
        nanopore_profile=opts.nanopore_profile,
    )
    simulators = opts.simulator_specs
    if opts.profile:
        sim_name, prof = PROFILE_MAP[opts.profile]
        simulators = [(sim_name, {})]
        if sim_name == "illumina":
            opts.illumina_profile = prof
        else:
            opts.nanopore_profile = prof
    elif simulators is None:
        simulators = [(name, {}) for name in opts.simulators]

    if opts.decay_rate is not None:
        simulators.append(DegradationChannel(deletion_prob=opts.decay_rate))

    updated: list[tuple[str, dict[str, object]]] = []
    for name, params in simulators:
        new_params = dict(params)
        if name == "illumina" or name.startswith("nanopore"):
            if opts.coverage is not None:
                new_params.setdefault("coverage", opts.coverage)
            if opts.quality_profile is not None:
                new_params.setdefault("quality_profile", opts.quality_profile)
        if name == "illumina":
            if opts.illumina_profile:
                prof = ILLUMINA_PROFILES.get(opts.illumina_profile)
                if prof is None:
                    logger.error("Unknown Illumina profile: %s", opts.illumina_profile)
                    raise SystemExit(1)
                for k, v in prof.items():
                    new_params.setdefault(k, v)
            if opts.illumina_profile_file:
                file_params = _load_profile_file(opts.illumina_profile_file)
                for k, v in file_params.items():
                    new_params.setdefault(k, v)
            if opts.illumina_depth is not None:
                new_params["coverage"] = opts.illumina_depth
            if opts.illumina_quality is not None:
                new_params["quality_profile"] = opts.illumina_quality
            if opts.illumina_context is not None:
                new_params["context_errors"] = opts.illumina_context
            if opts.illumina_sub_rate is not None:
                new_params["substitution_rate"] = opts.illumina_sub_rate
            if opts.illumina_ins_rate is not None:
                new_params["insertion_rate"] = opts.illumina_ins_rate
            if opts.illumina_del_rate is not None:
                new_params["deletion_rate"] = opts.illumina_del_rate
        if name.startswith("nanopore"):
            if opts.nanopore_profile:
                prof = NANOPORE_PROFILES.get(opts.nanopore_profile)
                if prof is None:
                    logger.error("Unknown Nanopore profile: %s", opts.nanopore_profile)
                    raise SystemExit(1)
                for k, v in prof.items():
                    new_params.setdefault(k, v)
            if opts.nanopore_profile_file:
                file_params = _load_profile_file(opts.nanopore_profile_file)
                for k, v in file_params.items():
                    new_params.setdefault(k, v)
            if opts.nanopore_depth is not None:
                new_params["coverage"] = opts.nanopore_depth
            if opts.nanopore_quality is not None:
                new_params["quality_profile"] = opts.nanopore_quality
            if opts.nanopore_context is not None:
                new_params["context_errors"] = opts.nanopore_context
            if opts.nanopore_sub_rate is not None:
                new_params["substitution_rate"] = opts.nanopore_sub_rate
            if opts.nanopore_ins_rate is not None:
                new_params["insertion_rate"] = opts.nanopore_ins_rate
            if opts.nanopore_del_rate is not None:
                new_params["deletion_rate"] = opts.nanopore_del_rate
        if name == "indel":
            if opts.indel_profile is not None:
                if opts.indel_profile not in INDEL_PROFILES:
                    logger.error("Unknown indel profile: %s", opts.indel_profile)
                    raise SystemExit(1)
                new_params.setdefault("profile", opts.indel_profile)
            if opts.sub_rate is not None:
                new_params["substitution_prob"] = opts.sub_rate
            if opts.ins_rate is not None:
                new_params["insertion_prob"] = opts.ins_rate
            if opts.del_rate is not None:
                new_params["deletion_prob"] = opts.del_rate
        if name == "simple" and opts.sub_rate is not None:
            new_params["error_rate"] = opts.sub_rate
        if name == "illumina_builtin" and opts.sub_rate is not None:
            new_params["error_rate"] = opts.sub_rate
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

    if args.profile is not None:
        sim_name, preset = PROFILE_MAP[args.profile]
        simulators = [(sim_name, {})]
        if sim_name == "illumina":
            cfg.illumina_profile = preset
        else:
            cfg.nanopore_profile = preset

    if args.illumina_profile is not None:
        cfg.illumina_profile = args.illumina_profile
    if args.nanopore_profile is not None:
        cfg.nanopore_profile = args.nanopore_profile
    if args.indel_profile is not None:
        if args.indel_profile not in INDEL_PROFILES:
            logger.error("Unknown indel profile: %s", args.indel_profile)
            raise SystemExit(1)
        for name, params in simulators:
            if name == "indel":
                params.setdefault("profile", args.indel_profile)
    if args.illumina_profile_file is not None:
        prof = _load_profile_file(args.illumina_profile_file)
        for name, params in simulators:
            if name == "illumina":
                for k, v in prof.items():
                    params.setdefault(k, v)
    if args.nanopore_profile_file is not None:
        prof = _load_profile_file(args.nanopore_profile_file)
        for name, params in simulators:
            if name.startswith("nanopore"):
                for k, v in prof.items():
                    params.setdefault(k, v)

    input_file = extra.get("input_file")
    output_file = extra.get("output_file")
    if not input_file or not output_file:
        logger.error("Config must define 'input' and 'output' paths")
        raise SystemExit(1)

    decay_rate = args.decay_rate if args.decay_rate is not None else extra.get("decay_rate")
    if decay_rate is not None:
        simulators.append(DegradationChannel(deletion_prob=decay_rate))

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


def _handle_list_profiles(_: argparse.Namespace) -> None:
    """Print available Illumina and Nanopore profiles."""

    print("Illumina profiles:")
    for name in sorted(ILLUMINA_PROFILES):
        print(f"  {name}")

    print("Nanopore profiles:")
    for name in sorted(NANOPORE_PROFILES):
        print(f"  {name}")

    print("Indel profiles:")
    for name in sorted(INDEL_PROFILES):
        print(f"  {name}")


def register_profiles_subcommand(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``profiles`` subcommand."""

    parser = subparsers.add_parser(
        "profiles", help="List available sequencing profiles"
    )
    parser.set_defaults(func=_handle_list_profiles)
