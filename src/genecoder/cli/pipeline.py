from __future__ import annotations

"""CLI helpers for the core encode/ECC/channel/decode pipeline."""

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, Mapping

from genecoder.simulators.illumina import ILLUMINA_PROFILES
from genecoder.simulators.nanopore import NANOPORE_PROFILES

from genecoder.channel_config import ChannelConfig
from genecoder.config.loader import load_mapping_file, validate_bundle_document
from genecoder.core import encode, decode, inspect_coding_plan
from genecoder.formats import SequenceBatch
from genecoder.parallel import parallel_map
from genecoder.plugin_manager import (
    CODEC_REGISTRY,
    FEC_REGISTRY,
    init_plugins,
)
from genecoder.simulators import SIMULATOR_REGISTRY, ChannelPipeline
from genecoder.simulators.batch_utils import (
    RESULT_COVERAGE_KEY,
    RESULT_DROPOUT_FLAG_KEY,
    RESULT_MUTATION_TOTALS_KEY,
    RESULT_SYNTHESIS_FLAG_KEY,
    clone_batch,
    finalize_batch_statistics,
    load_coverage_distribution,
    mutation_counts,
)
from genecoder.metrics import metrics as aggregate_metrics, set_metrics_path
from genecoder.synthesis import SynthesisConstraints
from genecoder.runtime import make_run_context
from genecoder.results.collector import (
    DecodeStageEvent,
    EncodeStageEvent,
    RunArtifactCollector,
    SimulateStageEvent,
)
from genecoder.constraints import load_constraint_policy
from genecoder.app import (
    ArtifactOutputPolicy,
    ChannelProfile,
    RunPipelineRequest,
    RunPipelineUseCase,
    SeedProfile,
)

RUN_PROFILE_VERSION = "2026.02"

logger = logging.getLogger(__name__)


def _parse_float(value: object, default: float | None = None) -> float | None:
    """Return ``value`` parsed as ``float`` falling back to ``default``."""

    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_int(value: object, default: int | None = None) -> int | None:
    """Return ``value`` parsed as ``int`` falling back to ``default``."""

    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def _is_truthy(value: object) -> bool:
    """Return ``True`` when ``value`` represents a truthy metadata flag."""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)



def _load_config(path: str) -> tuple[str, str | None, str | None, Dict[str, Any]]:
    """Parse pipeline settings from a YAML/JSON ``path``."""

    data = dict(load_mapping_file(path))
    validate_bundle_document({"encode": {"input_files": ["placeholder"], "method": "base4_direct"}, "simulate": data})

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


def _build_constraints_from_channel(channel_params: Mapping[str, Any]) -> SynthesisConstraints | None:
    """Return synthesis constraints defined in ``channel_params`` when present."""

    if not channel_params:
        return None
    try:
        policy = load_constraint_policy(channel_params)
        return SynthesisConstraints.from_policy(policy)
    except Exception:
        logger.warning("Ignoring invalid synthesis constraints in channel config")
        return None


def _constraints_limits(constraints: SynthesisConstraints | None) -> dict[str, float | int]:
    if constraints is None:
        return {}
    return {
        "min_length": constraints.min_length,
        "max_length": constraints.max_length,
        "max_homopolymer": constraints.max_homopolymer,
        "gc_min": constraints.gc_min,
        "gc_max": constraints.gc_max,
    }


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

    channel_params = dict(channel_params)
    constraints = _build_constraints_from_channel(channel_params)
    config_candidates = {
        key: channel_params.pop(key)
        for key in list(channel_params)
        if key
        in {
            "parallel",
            "workers",
            "use_process_pool",
            "use_mpi",
            "illumina_profile",
            "nanopore_profile",
            "dropout_rate",
            "coverage_distribution",
            "synthesis_loss",
        }
    }

    coverage_config = config_candidates.get("coverage_distribution")
    coverage_distribution = (
        load_coverage_distribution(coverage_config)
        if coverage_config is not None
        else None
    )
    channel_config = None
    if config_candidates or coverage_distribution is not None:
        channel_config = ChannelConfig(
            parallel=_is_truthy(config_candidates.get("parallel", False)),
            workers=_parse_int(config_candidates.get("workers")),
            use_process_pool=_is_truthy(config_candidates.get("use_process_pool", False)),
            use_mpi=_is_truthy(config_candidates.get("use_mpi", False)),
            illumina_profile=(
                str(config_candidates.get("illumina_profile"))
                if config_candidates.get("illumina_profile") is not None
                else None
            ),
            nanopore_profile=(
                str(config_candidates.get("nanopore_profile"))
                if config_candidates.get("nanopore_profile") is not None
                else None
            ),
            dropout_rate=_parse_float(config_candidates.get("dropout_rate")),
            coverage_distribution=coverage_distribution,
            synthesis_loss=_parse_float(config_candidates.get("synthesis_loss")),
        )

    channel_constructor_params = dict(channel_params)
    pipeline_channels: list[Any] = []
    channel_instance = None
    if channel and channel != "none":
        base_channel = SIMULATOR_REGISTRY[channel]
        if channel_constructor_params:
            try:
                channel_instance = type(base_channel)(**channel_constructor_params)
            except Exception as exc:
                logger.error(
                    "Invalid channel parameters for %s: %s", channel, exc
                )
                raise SystemExit(1)
        else:
            channel_instance = base_channel
        pipeline_channels.append(channel_instance)

    original_data = Path(input_path).read_bytes()
    dna_result, fec_info = encode(codec, fec, original_data)

    if isinstance(dna_result, SequenceBatch):
        original_batch = clone_batch(dna_result)
    else:
        header_parts = [f"method={codec}", f"input_file={Path(input_path).name}"]
        if fec:
            header_parts.append(f"fec={fec}")
        batch_id = f"pipeline-{Path(input_path).stem or 'batch'}"
        original_batch = SequenceBatch.build(
            [(" ".join(header_parts), dna_result)],
            batch_id=batch_id,
        )

    simulation_batch = clone_batch(original_batch)

    pipeline = ChannelPipeline(pipeline_channels)
    result = pipeline.simulate(simulation_batch, config=channel_config)
    if isinstance(result, SequenceBatch):
        mutated_batch = result
    else:
        header = simulation_batch.first_header() if simulation_batch.oligos else "pipeline"
        mutated_batch = SequenceBatch.build(
            [(header, str(result))],
            batch_id=simulation_batch.batch_id,

        )

    mutated_sequence = mutated_batch.primary_sequence()
    decoded = decode(codec, fec, mutated_sequence, fec_info)
    Path(output_path).write_bytes(decoded)

    if len(original_batch.oligos) != len(mutated_batch.oligos):
        logger.warning(
            "SequenceBatch oligo count changed after channel simulation: %s -> %s",
            len(original_batch.oligos),
            len(mutated_batch.oligos),
        )

    coverage_counts: list[int] = []
    dropout_flags: list[bool] = []
    synthesis_flags: list[bool] = []
    per_oligo_totals: list[tuple[int, int, int]] = []
    for idx, mutated_oligo in enumerate(mutated_batch.oligos):
        original_sequence = (
            original_batch.oligos[idx].sequence
            if idx < len(original_batch.oligos)
            else mutated_oligo.sequence
        )
        coverage_value = _parse_int(mutated_oligo.metadata.get(RESULT_COVERAGE_KEY))
        if coverage_value is None:
            coverage_value = 0 if not mutated_oligo.sequence else 1
            mutated_oligo.metadata[RESULT_COVERAGE_KEY] = str(coverage_value)
        coverage_counts.append(int(coverage_value))

        dropout_flag = _is_truthy(
            mutated_oligo.metadata.get(RESULT_DROPOUT_FLAG_KEY)
        )
        if RESULT_DROPOUT_FLAG_KEY not in mutated_oligo.metadata:
            dropout_flag = coverage_value <= 0 or mutated_oligo.sequence == ""
            mutated_oligo.metadata[RESULT_DROPOUT_FLAG_KEY] = (
                "true" if dropout_flag else "false"
            )
        dropout_flags.append(bool(dropout_flag))

        synthesis_flag = _is_truthy(
            mutated_oligo.metadata.get(RESULT_SYNTHESIS_FLAG_KEY)
        )
        if RESULT_SYNTHESIS_FLAG_KEY not in mutated_oligo.metadata:
            mutated_oligo.metadata[RESULT_SYNTHESIS_FLAG_KEY] = "false"
            synthesis_flag = False
        synthesis_flags.append(bool(synthesis_flag))

        totals_json = mutated_oligo.metadata.get(RESULT_MUTATION_TOTALS_KEY)
        totals_data: dict[str, Any] | None = None
        sub = ins = dele = 0
        if totals_json:
            try:
                parsed_totals = json.loads(totals_json)
            except (TypeError, ValueError, json.JSONDecodeError):
                parsed_totals = None
            if isinstance(parsed_totals, dict):
                totals_data = {
                    "substitutions": _parse_int(parsed_totals.get("substitutions"), 0)
                    or 0,
                    "insertions": _parse_int(parsed_totals.get("insertions"), 0) or 0,
                    "deletions": _parse_int(parsed_totals.get("deletions"), 0) or 0,
                }
                sub = int(totals_data["substitutions"])
                ins = int(totals_data["insertions"])
                dele = int(totals_data["deletions"])
        if totals_data is None:
            sub, ins, dele = mutation_counts(
                original_sequence, mutated_oligo.sequence
            )
            mutated_oligo.metadata[RESULT_MUTATION_TOTALS_KEY] = json.dumps(
                {
                    "substitutions": sub,
                    "insertions": ins,
                    "deletions": dele,
                }
            )
        per_oligo_totals.append((sub, ins, dele))

    finalize_batch_statistics(
        mutated_batch, coverage_counts, dropout_flags, synthesis_flags, per_oligo_totals
    )

    subs_total = sum(item[0] for item in per_oligo_totals)
    ins_total = sum(item[1] for item in per_oligo_totals)
    dels_total = sum(item[2] for item in per_oligo_totals)
    dropout_count = sum(1 for flag in dropout_flags if flag)

    avg_cov = _parse_float(mutated_batch.metadata.get("sim_average_coverage"))
    coverage_value = (
        int(round(avg_cov))
        if avg_cov is not None
        else (
            int(round(sum(coverage_counts) / max(1, len(coverage_counts))))
            if coverage_counts
            else None
        )
    )
    total_reads = _parse_int(mutated_batch.metadata.get("sim_total_reads"))

    mutation_totals_raw = mutated_batch.metadata.get("sim_mutation_totals")
    if isinstance(mutation_totals_raw, str) and mutation_totals_raw:
        try:
            parsed_totals = json.loads(mutation_totals_raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed_totals = None
        if isinstance(parsed_totals, dict):
            subs_total = int(parsed_totals.get("substitutions", subs_total))
            ins_total = int(parsed_totals.get("insertions", ins_total))
            dels_total = int(parsed_totals.get("deletions", dels_total))

    dropout_total_meta = _parse_int(
        mutated_batch.metadata.get("sim_dropout_total"), dropout_count
    )
    dropout_fraction = _parse_float(
        mutated_batch.metadata.get("sim_dropout_fraction"),
        dropout_count / max(1, len(mutated_batch.oligos)),
    )
    synthesis_total_meta = _parse_int(
        mutated_batch.metadata.get("sim_synthesis_failures"),
        sum(1 for flag in synthesis_flags if flag),
    )
    synthesis_fraction = _parse_float(
        mutated_batch.metadata.get("sim_synthesis_fraction"),
        sum(1 for flag in synthesis_flags if flag) / max(1, len(mutated_batch.oligos)),
    )

    collector = RunArtifactCollector(
        run_id=Path(input_path).stem or "pipeline-run",
        input_config={
            "codec": codec,
            "fec": fec,
            "channel": channel or "none",
            "channel_parameters": dict(channel_constructor_params),
        },
        reproducibility={
            "sim_seed": make_run_context().simulate_seed,
            "batch_seed": mutated_batch.seed,
        },
    )
    collector.record_encode(
        EncodeStageEvent(
            codec=codec,
            fec=fec,
            input_path=input_path,
            original_data=original_data,
            encoded_batch=original_batch,
            fec_info=fec_info,
            encoding_parameters={"method": codec, **({"fec": fec} if fec else {})},
        )
    )
    collector.record_simulate(
        SimulateStageEvent(
            channel=channel,
            channel_parameters=dict(channel_constructor_params),
            mutated_batch=mutated_batch,
            substitutions=subs_total,
            insertions=ins_total,
            deletions=dels_total,
            coverage=coverage_value,
        )
    )
    collector.record_decode(
        DecodeStageEvent(output_path=output_path, decoded_data=decoded, constraints=constraints)
    )
    artifact = collector.emit()
    artifact.setdefault("input_config", {}).update(
        {
            "channel_runtime": {
                "dropout_count": dropout_total_meta,
                "dropout_fraction": dropout_fraction,
                "synthesis_failures": synthesis_total_meta,
                "synthesis_fraction": synthesis_fraction,
                "total_reads": total_reads,
            }
        }
    )
    if isinstance(artifact.get("outcome"), dict):
        embedded = artifact["outcome"].setdefault("metrics", {})
        if isinstance(embedded, dict):
            oligo = embedded.setdefault("oligo_metrics", {})
            if isinstance(oligo, dict):
                oligo.setdefault("coverage_counts", coverage_counts)
                oligo.setdefault("dropout_flags", [bool(flag) for flag in dropout_flags])
                oligo.setdefault(
                    "mutation_totals",
                    [
                        {
                            "substitutions": subs,
                            "insertions": ins,
                            "deletions": dele,
                        }
                        for subs, ins, dele in per_oligo_totals
                    ],
                )
            embedded.setdefault(
                "sequence_batch",
                {
                    "batch_id": mutated_batch.batch_id,
                    "seed": mutated_batch.seed,
                    "metadata": dict(mutated_batch.metadata),
                },
            )

    return artifact



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
    parser.add_argument(
        "--metrics-path",
        type=str,
        help="Path to the aggregate metrics JSON file",
    )
    parser.add_argument(
        "--emit-manifest-report",
        action="store_true",
        help="Generate HTML reports for decoded manifests",
    )
    parser.add_argument(
        "--launch-dashboard",
        action="store_true",
        help="Launch the dashboard for the metrics file after the run",
    )
    parser.add_argument(
        "--explain-coding-stack",
        action="store_true",
        help="Emit planner diagnostics describing selected/rejected coding stack layers.",
    )

    parser.set_defaults(func=_handle_command)


def _handle_command(args: argparse.Namespace) -> None:
    metrics_override: Path | None = None
    if args.metrics_path:
        metrics_override = Path(args.metrics_path)
        set_metrics_path(metrics_override)

    def _launch_dashboard_if_requested() -> None:
        if not args.launch_dashboard:
            return
        target = metrics_override or aggregate_metrics.path
        if not target.exists():
            logger.warning(
                "Metrics file %s not found, skipping dashboard launch", target
            )
            return
        from genecoder.dashboard_streamlit import launch

        launch(str(target))

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

    if args.explain_coding_stack:
        explanation = inspect_coding_plan(
            {
                "codec": codec,
                "fec": fec,
                "coding": {"channel_errors": ["substitution", "insertion", "deletion"]},
            }
        )
        logger.info("Coding planner: %s", json.dumps(explanation, indent=2, sort_keys=True))

    def _execute() -> Dict[str, Any]:
        response = RunPipelineUseCase().execute(
            RunPipelineRequest(
                codec=codec,
                fec=fec,
                channel=channel,
                input_path=args.input,
                output_path=args.output,
                profile=(ChannelProfile(name=channel, parameters=channel_params) if channel and channel != "none" else None),
                seeds=SeedProfile(global_seed=args.seed),
                artifacts=ArtifactOutputPolicy(
                    metrics_path=(str(metrics_override) if metrics_override else None),
                    emit_manifest=True,
                    emit_html_report=bool(args.emit_manifest_report),
                ),
            )
        )
        artifact = dict(response.run_schema)
        artifact.setdefault("schema_provenance", {}).update(
            {
                "seed": args.seed,
                "profile_version": RUN_PROFILE_VERSION,
                "command_lineage": ["genecli pipeline", "encode", "simulate", "decode"],
            }
        )
        return artifact

    if args.mpi_workers:
        parallel_map(
            lambda _: _execute(),
            [None],
            workers=args.mpi_workers,
            use_mpi=True,
        )[0]
    else:
        _execute()

    metrics_path = Path(str(metrics_override) if metrics_override else str(args.output) + ".json")
    logger.info("Run artifact written to %s", metrics_path)

    manifest_path = metrics_path.with_suffix(".manifest.json")
    if manifest_path.exists():
        logger.info("Manifest written to %s", manifest_path)

    if args.emit_manifest_report:
        html_report_path = metrics_path.with_suffix(".html")
        if html_report_path.exists():
            logger.info("HTML report written to %s", html_report_path)

    _launch_dashboard_if_requested()
