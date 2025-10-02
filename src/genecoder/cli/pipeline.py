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

from genecoder.channel_config import ChannelConfig
from genecoder.core import encode, decode, metrics as gather_metrics
from genecoder.formats import SequenceBatch
from genecoder.html_report import generate_html_report
from genecoder.manifest import generate_manifest
from genecoder.parallel import parallel_map
from genecoder.plugin_manager import (
    CODEC_REGISTRY,
    FEC_REGISTRY,
    yaml as yaml_module,
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

    channel_params = dict(channel_params)
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

    coverage_hist_raw = mutated_batch.metadata.get("sim_coverage_histogram")
    coverage_hist: dict[str, int] = {}
    if isinstance(coverage_hist_raw, str) and coverage_hist_raw:
        try:
            parsed_hist = json.loads(coverage_hist_raw)
            if isinstance(parsed_hist, dict):
                coverage_hist = {
                    str(key): int(_parse_int(value, 0) or 0)
                    for key, value in parsed_hist.items()
                }
        except (TypeError, ValueError, json.JSONDecodeError):
            coverage_hist = {}

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

    metrics: dict[str, Any] = gather_metrics(
        mutated_sequence,
        original_data,
        decoded,
        fec,
        subs_total,
        ins_total,
        dels_total,
        coverage_value,
        oligos=[ol.sequence for ol in mutated_batch.oligos],
        dropout_flags=dropout_flags,
    )

    oligo_metrics = metrics.setdefault("oligo_metrics", {})
    oligo_metrics.setdefault("coverage_counts", coverage_counts)
    oligo_metrics.setdefault(
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
    oligo_metrics.setdefault(
        "synthesis_failures", [bool(flag) for flag in synthesis_flags]
    )

    channel_configuration: dict[str, Any] = {}
    if channel_config is not None:
        channel_configuration = {
            "parallel": channel_config.parallel,
            "workers": channel_config.workers,
            "use_process_pool": channel_config.use_process_pool,
            "use_mpi": channel_config.use_mpi,
            "illumina_profile": channel_config.illumina_profile,
            "nanopore_profile": channel_config.nanopore_profile,
            "dropout_rate": channel_config.dropout_rate,
            "coverage_distribution": (
                dict(channel_config.coverage_distribution)
                if channel_config.coverage_distribution
                else None
            ),
            "synthesis_loss": channel_config.synthesis_loss,
        }

    channel_metrics: dict[str, Any] = {
        "name": channel or "none",
        "dropout": {
            "count": dropout_total_meta,
            "fraction": dropout_fraction,
        },
        "coverage": {
            "average": avg_cov
            if avg_cov is not None
            else (
                sum(coverage_counts) / max(1, len(coverage_counts))
                if coverage_counts
                else None
            ),
            "total_reads": total_reads,
            "histogram": coverage_hist,
        },
        "synthesis": {
            "count": synthesis_total_meta,
            "fraction": synthesis_fraction,
        },
        "mutation_totals": {
            "substitutions": subs_total,
            "insertions": ins_total,
            "deletions": dels_total,
        },
        "oligo_count": len(mutated_batch.oligos),
    }
    if channel_configuration:
        channel_metrics["configuration"] = channel_configuration
    if channel_constructor_params:
        channel_metrics["parameters"] = channel_constructor_params

    metrics["channel"] = channel_metrics
    metrics["dropout_count"] = dropout_total_meta
    metrics["dropout_fraction"] = dropout_fraction
    metrics["sequence_batch"] = {
        "batch_id": mutated_batch.batch_id,
        "seed": mutated_batch.seed,
        "metadata": dict(mutated_batch.metadata),
    }

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
