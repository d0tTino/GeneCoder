from __future__ import annotations

"""Combine simulators and synthesis constraints into a single channel."""

import argparse
import json
import logging
import os
import random
import shlex
from pathlib import Path
from typing import Sequence, Dict, Any, Mapping


from genecoder.formats import SequenceBatch
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.channel_engine import ChannelPipeline
from genecoder.channel_config import ChannelConfig
from genecoder.channels.base import BaseChannel
from genecoder.synthesis import SynthesisConstraints, validate_sequence
from genecoder.constraints import ConstraintEngine, ConstraintRepairPipeline, load_constraint_policy
from genecoder.error_simulation import introduce_errors
from genecoder.metrics import metrics
from genecoder.simulators.illumina import ILLUMINA_PROFILES
from genecoder.simulators.nanopore import NANOPORE_PROFILES, DNARSIM_RATE_TABLES
from genecoder.error_simulation import (
    ADAPTER_PROFILES,
    DEFAULT_ADAPTER_PROFILE,
    INDEL_PROFILES,
)
from genecoder.runtime import make_run_context
from genecoder.config.loader import (
    PROFILE_ALIAS_TABLE,
    load_channel_workflow_config,
    load_mapping_file,
    resolve_channel_profile_alias,
)
from genecoder.simulators.batch_utils import (
    RESULT_COVERAGE_KEY,
    RESULT_DROPOUT_FLAG_KEY,
    RESULT_MUTATION_LOG_KEY,
    RESULT_MUTATION_TOTALS_KEY,
    RESULT_SYNTHESIS_FLAG_KEY,
    bool_to_str,
    clone_batch,
    finalize_batch_statistics,
    mutation_counts,
)
from .options import ChannelOptions, build_channel_options, _parse_distribution
from .shared import add_single_io_args

logger = logging.getLogger(__name__)



PROFILE_MAP = PROFILE_ALIAS_TABLE

def _normalize_stage_options(value: object) -> list[str]:
    """Return ``value`` as a list of command-line options."""

    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            return [opt for opt in shlex.split(value) if opt]
        except ValueError:
            return [chunk for chunk in value.split() if chunk]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [str(opt) for opt in value if str(opt)]
    return [str(value)]


def _extract_stage_parameters(
    params: Dict[str, Any]
) -> tuple[Dict[str, Any], str | None, list[str]]:
    """Split stage-related keys from simulator ``params``."""

    clean_params = dict(params)
    stage_raw = None
    for key in ("stage", "stage_name"):
        if key in clean_params:
            stage_raw = clean_params.pop(key)
            break
    stage = None
    if stage_raw is not None:
        stage = str(stage_raw).strip() or None

    options_raw = None
    for key in ("options", "stage_options", "flags", "cli_options"):
        if key in clean_params:
            options_raw = clean_params.pop(key)
            break

    options = _normalize_stage_options(options_raw)
    return clean_params, stage, options


def _load_config(
    path: str,
) -> tuple[
    list[tuple[str, Dict[str, Any]]],
    dict[str, int],
    ChannelConfig,
    dict[str, Any],
]:
    workflow = load_channel_workflow_config(path)
    simulators: list[tuple[str, Dict[str, Any]]] = []
    for stage in workflow.simulators:
        params = dict(stage.parameters)
        if stage.stage:
            params["stage"] = stage.stage
        if stage.options:
            params["options"] = list(stage.options)
        simulators.append((stage.name, params))
    constraints = workflow.constraints.to_policy_dict()
    cfg = workflow.pipeline.to_channel_config()
    extra = {
        "input_file": workflow.input_file,
        "output_file": workflow.output_file,
        "sub_prob": workflow.sub_prob,
        "ins_prob": workflow.ins_prob,
        "del_prob": workflow.del_prob,
        "seed": workflow.seed,
        "batch_workers": workflow.batch_workers,
    }
    if workflow.decay_rate is not None:
        extra["decay_rate"] = workflow.decay_rate
    return simulators, constraints, cfg, extra


def _load_profile_file(path: str) -> Dict[str, Any]:
    """Return parameters from JSON or YAML ``path``."""
    return dict(load_mapping_file(path))


def _apply_simulators(
    batch: SequenceBatch,
    simulators: Sequence[
        BaseChannel | tuple[str, Dict[str, Any]]
    ],
    *,
    config: ChannelConfig,
    seed: int | None = None,
) -> tuple[SequenceBatch, list[dict[str, Any]]]:
    named_channels: list[tuple[str, BaseChannel]] = []
    stages: list[dict[str, Any]] = []
    for item in simulators:
        if isinstance(item, BaseChannel):
            channel = item
            name = channel.__class__.__name__
            stage_label = getattr(channel, "stage", None)
            options = list(getattr(channel, "options", ()))
            params_view: dict[str, Any] = {}
            if hasattr(channel, "error_rate"):
                params_view["error_rate"] = getattr(channel, "error_rate")
            stage_info: dict[str, Any] = {"name": name}
            if stage_label:
                stage_info["stage"] = stage_label
            if params_view:
                stage_info["parameters"] = params_view
            if options:
                stage_info["options"] = options
            stages.append(stage_info)
        else:
            name, params = item
            if name not in SIMULATOR_REGISTRY:
                logger.error("Unknown simulator: %s", name)
                raise SystemExit(1)
            channel_template = SIMULATOR_REGISTRY[name]
            clean_params, stage, options = _extract_stage_parameters(params)
            stage_info: dict[str, Any] = {"name": name}
            if clean_params:
                stage_info["parameters"] = clean_params
            if stage:
                stage_info["stage"] = stage
            if options:
                stage_info["options"] = options
            try:
                if name == "desp":
                    channel = type(channel_template)(
                        **clean_params,
                        stage=stage,
                        options=options or None,
                    )
                else:
                    channel = type(channel_template)(**clean_params)
            except Exception as exc:
                logger.error("Invalid parameters for %s: %s", name, exc)
                raise SystemExit(1)
            stages.append(stage_info)
        named_channels.append((name, channel))
        logger.info("Applied %s simulator", name)

    profile_map: dict[str, str] = {}
    if config.illumina_profile:
        profile_map["sequencing"] = config.illumina_profile
    elif config.nanopore_profile:
        profile_map["sequencing"] = config.nanopore_profile

    pipeline = ChannelPipeline.from_simulators(named_channels)
    final, provenance = pipeline.run(
        batch,
        profile=profile_map,
        run_context=make_run_context(global_seed=seed),
        config=config,
    )
    final.metadata["sim_stage_provenance"] = json.dumps(provenance)

    merged_stages: list[dict[str, Any]] = []
    for idx, stage in enumerate(stages):
        merged = dict(stage)
        if idx < len(provenance):
            merged.update(provenance[idx])
        merged_stages.append(merged)
    return final, merged_stages


def _batch_from_string(sequence: str) -> SequenceBatch:
    batch = SequenceBatch.build([("cli", sequence)], batch_id="cli")
    if batch.oligos:
        oligo = batch.oligos[0]
        oligo.metadata[RESULT_COVERAGE_KEY] = "1"
        oligo.metadata[RESULT_DROPOUT_FLAG_KEY] = bool_to_str(False)
        oligo.metadata[RESULT_SYNTHESIS_FLAG_KEY] = bool_to_str(False)
        oligo.metadata[RESULT_MUTATION_LOG_KEY] = json.dumps([])
        oligo.metadata[RESULT_MUTATION_TOTALS_KEY] = json.dumps(
            {"substitutions": 0, "insertions": 0, "deletions": 0}
        )
        finalize_batch_statistics(batch, [1], [False], [False], [(0, 0, 0)])
    return batch


def _is_flag_true(metadata: Mapping[str, str], key: str) -> bool:
    return metadata.get(key, "").strip().lower() in {"true", "1", "yes"}


def _parse_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _parse_int(value: str | None, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        try:
            return int(float(value)) if value is not None else default
        except (TypeError, ValueError):
            return default


def _resolve_sim_seed(seed: int | None) -> int | None:
    return make_run_context(global_seed=seed).simulate_seed


def _simulate_probabilities(
    batch: SequenceBatch,
    *,
    sub_prob: float,
    ins_prob: float,
    del_prob: float,
    seed: int | None,
) -> SequenceBatch:
    base_rng = random.Random(seed)
    mutated = clone_batch(batch)
    coverage_counts: list[int] = []
    dropout_flags: list[bool] = []
    synthesis_flags: list[bool] = []
    consensus_totals: list[tuple[int, int, int]] = []

    for idx, (original, oligo) in enumerate(zip(batch.oligos, mutated.oligos), start=1):
        if seed is not None:
            rng = random.Random(seed + idx)
        else:
            rng = random.Random(base_rng.random())
        attempts = 0
        while True:
            mutated_seq = introduce_errors(
                original.sequence,
                substitution_prob=sub_prob,
                insertion_prob=ins_prob,
                deletion_prob=del_prob,
                rng=rng,
            )
            subs, ins, dels = _count_errors(original.sequence, mutated_seq)
            attempts += 1
            if (
                attempts >= 50
                or ins_prob == 0.0
                and del_prob == 0.0
                or ins != 0
                or dels != 0
            ):
                break
        if ins == 0 and dels == 0 and (ins_prob > 0 or del_prob > 0):
            seq_list = list(mutated_seq)
            if del_prob >= ins_prob and seq_list:
                pos = rng.randrange(len(seq_list))
                seq_list.pop(pos)
                dels = 1
            else:
                pos = rng.randrange(len(seq_list) + 1)
                seq_list.insert(pos, rng.choice("ATGC"))
                ins = 1
            mutated_seq = "".join(seq_list)
        if (
            (ins_prob > 0 or del_prob > 0)
            and len(mutated_seq) == len(original.sequence)
            and mutated_seq
        ):
            seq_list = list(mutated_seq)
            if del_prob >= ins_prob and len(seq_list) > 1:
                pos = rng.randrange(len(seq_list))
                seq_list.pop(pos)
            else:
                pos = rng.randrange(len(seq_list) + 1)
                seq_list.insert(pos, rng.choice("ATGC"))
            mutated_seq = "".join(seq_list)
        oligo.sequence = mutated_seq
        oligo.metadata[RESULT_COVERAGE_KEY] = "1"
        oligo.metadata[RESULT_DROPOUT_FLAG_KEY] = bool_to_str(False)
        oligo.metadata[RESULT_SYNTHESIS_FLAG_KEY] = bool_to_str(False)
        oligo.metadata[RESULT_MUTATION_LOG_KEY] = json.dumps(
            [
                {
                    "read": mutated_seq,
                    "substitutions": subs,
                    "insertions": ins,
                    "deletions": dels,
                }
            ]
        )
        oligo.metadata[RESULT_MUTATION_TOTALS_KEY] = json.dumps(
            {"substitutions": subs, "insertions": ins, "deletions": dels}
        )
        coverage_counts.append(1)
        dropout_flags.append(False)
        synthesis_flags.append(False)
        consensus_totals.append((subs, ins, dels))

    finalize_batch_statistics(
        mutated, coverage_counts, dropout_flags, synthesis_flags, consensus_totals
    )
    metrics.increment("oligos_simulated")
    return mutated


def _count_errors(original: str, mutated: str) -> tuple[int, int, int]:
    """Return substitution, insertion and deletion counts."""

    return mutation_counts(original, mutated)


def process_channel(
    input_file: str,
    output_file: str,
    simulators: Sequence[BaseChannel | tuple[str, Dict[str, Any]]],
    constraints: dict[str, float | int],
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

    try:
        batch = SequenceBatch.from_fasta(fasta_str)
    except ValueError as exc:
        logger.error("Failed to parse %s: %s", input_file, exc)
        raise SystemExit(1)

    if not batch.oligos:
        logger.error("No FASTA records found in %s", input_file)
        raise SystemExit(1)

    policy = load_constraint_policy(constraints if constraints else None, fallback={"gc_min": 0.0, "gc_max": 1.0})
    synth = SynthesisConstraints.from_policy(policy)
    constraint_engine = ConstraintEngine(policy.to_rule_set())
    repair_pipeline = ConstraintRepairPipeline(policy)

    cfg = config or ChannelConfig()
    stage_metadata: list[dict[str, Any]] = []
    if simulators:
        processed_batch, stage_metadata = _apply_simulators(
            batch, simulators, config=cfg, seed=seed
        )
    else:
        processed_batch = _simulate_probabilities(
            batch,
            sub_prob=sub_prob,
            ins_prob=ins_prob,
            del_prob=del_prob,
            seed=seed,
        )

    total_len = sum(len(ol.sequence) for ol in processed_batch.oligos)
    sub_total = ins_total = del_total = 0
    dropout_count = 0
    synth_failures = 0

    for original, processed in zip(batch.oligos, processed_batch.oligos):
        dropout = _is_flag_true(processed.metadata, RESULT_DROPOUT_FLAG_KEY)
        synth_fail = _is_flag_true(processed.metadata, RESULT_SYNTHESIS_FLAG_KEY)
        if dropout:
            dropout_count += 1
        if synth_fail:
            synth_failures += 1
        pre_report = constraint_engine.validate(original.sequence)
        processed.metadata["constraint_report_pre"] = {
            "count": pre_report.count,
            "score": pre_report.score,
            "violations": [v.rule_id for v in pre_report.violations],
        }
        if dropout or synth_fail:
            continue
        repaired = repair_pipeline.run(processed.sequence)
        if repaired.repair is not None:
            processed.sequence = repaired.sequence
            processed.metadata["constraint_repair"] = {
                "strategy": repaired.repair.strategy,
                "changes": len(repaired.repair.changes),
                "reason": repaired.repair.reason,
            }
        post_report = constraint_engine.validate(processed.sequence)
        processed.metadata["constraint_report_post"] = {
            "count": post_report.count,
            "score": post_report.score,
            "violations": [v.rule_id for v in post_report.violations],
        }
        if not validate_sequence(processed.sequence, synth):
            raise ValueError("Sequence violates synthesis constraints")
        totals_json = processed.metadata.get(RESULT_MUTATION_TOTALS_KEY)
        totals = None
        if totals_json:
            try:
                totals = json.loads(totals_json)
            except json.JSONDecodeError:
                totals = None
        if totals:
            sub_total += int(totals.get("substitutions", 0))
            ins_total += int(totals.get("insertions", 0))
            del_total += int(totals.get("deletions", 0))
        else:
            s, i, d = _count_errors(original.sequence, processed.sequence)
            sub_total += s
            ins_total += i
            del_total += d
        logger.info("Sequence satisfies synthesis constraints")

    fasta_out = processed_batch.to_fasta(line_width=80)
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f_out:
        f_out.write(fasta_out)

    if stage_metadata:
        processed_batch.metadata["sim_stages"] = json.dumps(stage_metadata)

    coverage_hist = {}
    coverage_raw = processed_batch.metadata.get("sim_coverage_histogram")
    if coverage_raw:
        try:
            coverage_hist = json.loads(coverage_raw)
        except json.JSONDecodeError:
            coverage_hist = {}

    mutation_totals_raw = processed_batch.metadata.get("sim_mutation_totals")
    mutation_totals: dict[str, int] | None = None
    if mutation_totals_raw:
        try:
            parsed = json.loads(mutation_totals_raw)
            mutation_totals = {
                "substitutions": int(parsed.get("substitutions", sub_total)),
                "insertions": int(parsed.get("insertions", ins_total)),
                "deletions": int(parsed.get("deletions", del_total)),
            }
        except (json.JSONDecodeError, TypeError, ValueError):
            mutation_totals = None

    dropout_total_meta = _parse_int(
        processed_batch.metadata.get("sim_dropout_total"), dropout_count
    )
    dropout_fraction = _parse_float(
        processed_batch.metadata.get("sim_dropout_fraction"),
        dropout_count / max(1, len(processed_batch.oligos)),
    )
    synthesis_total_meta = _parse_int(
        processed_batch.metadata.get("sim_synthesis_failures"), synth_failures
    )
    synthesis_fraction = _parse_float(
        processed_batch.metadata.get("sim_synthesis_fraction"),
        synth_failures / max(1, len(processed_batch.oligos)),
    )

    manifest_simulators: list[str] = []
    for item in simulators:
        if isinstance(item, tuple):
            manifest_simulators.append(item[0])
        else:
            manifest_simulators.append(item.__class__.__name__)

    manifest = {
        "file": os.path.basename(Path(input_file).as_posix()),
        "simulators": manifest_simulators,
        "probabilities": {
            "sub_prob": sub_prob,
            "ins_prob": ins_prob,
            "del_prob": del_prob,
        },
        "constraint_policy": policy.to_dict(),
        "constraints": policy.to_dict(),
        "metrics": {
            "length": total_len,
            "substitutions": sub_total,
            "insertions": ins_total,
            "deletions": del_total,
        },
        "coverage": {
            "average": _parse_float(processed_batch.metadata.get("sim_average_coverage")),
            "histogram": coverage_hist,
            "total_reads": _parse_int(processed_batch.metadata.get("sim_total_reads")),
        },
        "dropout": {
            "count": dropout_total_meta,
            "fraction": dropout_fraction,
        },
        "synthesis": {
            "count": synthesis_total_meta,
            "fraction": synthesis_fraction,
        },
    }
    run_context = make_run_context(global_seed=seed)
    sim_seed = run_context.simulate_seed
    if sim_seed is not None:
        manifest["simulator_seed"] = sim_seed
    manifest["seed_provenance"] = run_context.seed_provenance()
    if mutation_totals is not None:
        manifest["mutation_totals"] = mutation_totals
    if stage_metadata:
        manifest["stages"] = stage_metadata

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
    dnarsim_profiles = ", ".join(sorted(DNARSIM_RATE_TABLES))
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
        help=(
            "Named Illumina profile or path to JSON/YAML file. "
            f"Available profiles: {illumina_profiles}"
        ),
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
        "--dnarsim-profile",
        type=str,
        default=None,
        help=f"Named DNArSim profile to use. Available profiles: {dnarsim_profiles}",
    )
    run_parser.add_argument(
        "--decay-rate",
        type=float,
        default=None,
        help="Probability of strand loss and damage",
    )
    run_parser.add_argument(
        "--dropout-rate",
        type=float,
        default=None,
        help="Probability that an oligo drops out before sequencing",
    )
    run_parser.add_argument(
        "--coverage-distribution",
        type=str,
        default=None,
        help="Coverage distribution mapping or JSON/YAML file",
    )
    run_parser.add_argument(
        "--synthesis-loss",
        type=float,
        default=None,
        help="Probability of synthesis failure per oligo",
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
            help=(
                "Substitution rate for generic simulators. "
                "When mapped to legacy error_rate, the value is applied to "
                "substitution/insertion/deletion equally (clamped so total ≤ 1.0)."
            ),
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
        target.add_argument(
            "--illumina-profile",
            type=str,
            default=None,
            help="Named Illumina profile or path to JSON/YAML file",
        )
        target.add_argument("--nanopore-depth", type=int, default=None, help="Coverage depth for Nanopore reads")
        target.add_argument("--nanopore-quality", type=str, default=None, help="Comma-separated quality profile or path to JSON")
        target.add_argument("--nanopore-context", type=str, default=None, help="Path to JSON/YAML context error map")
        target.add_argument("--nanopore-sub-rate", type=float, default=None, help="Substitution rate for Nanopore reads")
        target.add_argument("--nanopore-ins-rate", type=float, default=None, help="Insertion rate for Nanopore reads")
        target.add_argument("--nanopore-del-rate", type=float, default=None, help="Deletion rate for Nanopore reads")
        target.add_argument("--nanopore-profile", type=str, default=None, help="Named Nanopore profile to use")
        target.add_argument("--nanopore-profile-file", type=str, default=None, help="YAML file with Nanopore simulator parameters")
        target.add_argument("--dnarsim-profile", type=str, default=None, help="Named DNArSim profile to use")
        target.add_argument("--indel-profile", type=str, default=None, help="Named indel profile to use")
        target.add_argument(
            "--decay-rate",
            type=float,
            default=None,
            help="Probability of strand loss and damage",
        )
        target.add_argument(
            "--dropout-rate",
            type=float,
            default=None,
            help="Probability that an oligo drops out before sequencing",
        )
        target.add_argument(
            "--coverage-distribution",
            type=str,
            default=None,
            help="Coverage distribution mapping or JSON/YAML file",
        )
        target.add_argument(
            "--synthesis-loss",
            type=float,
            default=None,
            help="Probability of synthesis failure per oligo",
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
        dropout_rate=opts.dropout_rate,
        coverage_distribution=(
            dict(opts.coverage_distribution) if opts.coverage_distribution else None
        ),
        synthesis_loss=opts.synthesis_loss,
    )
    simulators = opts.simulator_specs
    if opts.profile:
        sim_name, prof = resolve_channel_profile_alias(opts.profile)
        simulators = [(sim_name, {})]
        if sim_name == "illumina":
            opts.illumina_profile = prof
        elif sim_name == "nanopore_dnarsim":
            opts.dnarsim_profile = prof
        else:
            opts.nanopore_profile = prof
    elif simulators is None:
        simulators = [(name, {}) for name in opts.simulators]

    if opts.decay_rate is not None:
        simulators.append(("decay", {"deletion_prob": opts.decay_rate}))

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
                new_params.setdefault("profile", opts.illumina_profile)
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
            selected_profile = opts.nanopore_profile
            profile_source = NANOPORE_PROFILES
            if name == "nanopore_dnarsim":
                selected_profile = opts.dnarsim_profile or opts.nanopore_profile
                profile_source = DNARSIM_RATE_TABLES

            if selected_profile:
                prof = profile_source.get(selected_profile)
                if prof is None:
                    label = "DNArSim" if name == "nanopore_dnarsim" else "Nanopore"
                    logger.error("Unknown %s profile: %s", label, selected_profile)
                    raise SystemExit(1)
                for k, v in prof.items():
                    new_params.setdefault(k, v)
                if name == "nanopore_dnarsim":
                    new_params.setdefault("profile", selected_profile)

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
            if name == "nanopore_dnarsim":
                for unsupported in ("insertion_profile", "deletion_profile"):
                    new_params.pop(unsupported, None)
        if name == "indel":
            indel_profile = opts.indel_profile
            if indel_profile is None and not any(
                rate is not None
                for rate in (opts.sub_rate, opts.ins_rate, opts.del_rate)
            ):
                indel_profile = DEFAULT_ADAPTER_PROFILE
            if indel_profile is not None:
                if indel_profile not in INDEL_PROFILES and indel_profile not in ADAPTER_PROFILES:
                    logger.error("Unknown indel profile: %s", indel_profile)
                    raise SystemExit(1)
                new_params.setdefault("profile", indel_profile)
            if opts.sub_rate is not None:
                new_params["substitution_prob"] = opts.sub_rate
            if opts.ins_rate is not None:
                new_params["insertion_prob"] = opts.ins_rate
            if opts.del_rate is not None:
                new_params["deletion_prob"] = opts.del_rate
        if name == "simple" and opts.sub_rate is not None:
            new_params["substitution_prob"] = opts.sub_rate
        if name == "illumina_builtin":
            if opts.sub_rate is not None:
                new_params["error_rate"] = opts.sub_rate
            if opts.illumina_depth is not None:
                new_params["coverage_depth"] = opts.illumina_depth
            if opts.illumina_quality is not None:
                new_params["quality_distribution"] = opts.illumina_quality
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
        sim_name, preset = resolve_channel_profile_alias(args.profile)
        simulators = [(sim_name, {})]
        if sim_name == "illumina":
            cfg.illumina_profile = preset
        else:
            cfg.nanopore_profile = preset

    if args.illumina_profile is not None:
        cfg.illumina_profile = args.illumina_profile
    if args.nanopore_profile is not None:
        cfg.nanopore_profile = args.nanopore_profile
    if args.dropout_rate is not None:
        cfg.dropout_rate = args.dropout_rate
    if args.synthesis_loss is not None:
        cfg.synthesis_loss = args.synthesis_loss
    if args.coverage_distribution is not None:
        cfg.coverage_distribution = _parse_distribution(args.coverage_distribution)
    if args.dnarsim_profile is not None:
        for name, params in simulators:
            if name == "nanopore_dnarsim":
                params.setdefault("profile", args.dnarsim_profile)
    if args.indel_profile is not None:
        if args.indel_profile not in INDEL_PROFILES and args.indel_profile not in ADAPTER_PROFILES:
            logger.error("Unknown indel profile: %s", args.indel_profile)
            raise SystemExit(1)
        for name, params in simulators:
            if name == "indel":
                params.setdefault("profile", args.indel_profile)
    else:
        for name, params in simulators:
            if name == "indel" and "profile" not in params:
                if any(
                    key in params
                    for key in ("substitution_prob", "insertion_prob", "deletion_prob", "error_rate")
                ):
                    continue
                params.setdefault("profile", DEFAULT_ADAPTER_PROFILE)
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
        simulators.append(("decay", {"deletion_prob": decay_rate}))

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


def list_profiles() -> None:
    """Print available Illumina and Nanopore profiles."""

    print("Illumina profiles:")
    for name in sorted(ILLUMINA_PROFILES):
        print(f"  {name}")

    print("Nanopore profiles:")
    for name in sorted(NANOPORE_PROFILES):
        print(f"  {name}")


def _handle_list_profiles(_: argparse.Namespace) -> None:
    """CLI handler for ``list-profiles``."""

    list_profiles()


def register_profiles_subcommand(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``channel list-profiles`` subcommand."""

    channel_parser = subparsers.choices.get("channel")
    if channel_parser is None:  # pragma: no cover - defensive
        return

    channel_subparsers: argparse._SubParsersAction[argparse.ArgumentParser] | None = None
    for action in channel_parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            channel_subparsers = action
            break
    if channel_subparsers is None:  # pragma: no cover - defensive
        channel_subparsers = channel_parser.add_subparsers(dest="channel_command")

    parser = channel_subparsers.add_parser(
        "list-profiles", help="List available sequencing profiles"
    )
    parser.set_defaults(func=_handle_list_profiles)
