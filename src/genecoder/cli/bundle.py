from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import os
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from dataclasses import dataclass, fields, asdict
from typing import Any, Mapping, Sequence, cast

import importlib.util

def _has_jsonschema() -> bool:
    try:
        return importlib.util.find_spec("jsonschema") is not None
    except (ValueError, ModuleNotFoundError):
        return False


_HAS_JSONSCHEMA = _has_jsonschema()

if _HAS_JSONSCHEMA:
    from jsonschema import Draft202012Validator, ValidationError
    from jsonschema.exceptions import best_match
else:  # pragma: no cover - used when jsonschema is unavailable
    class ValidationError(Exception):
        """Fallback validation error when jsonschema is unavailable."""

    class Draft202012Validator:
        """No-op schema validator used when jsonschema is unavailable."""

        def __init__(self, _schema: object) -> None:
            self._schema = _schema

        def iter_errors(self, _instance: object):
            return iter(())

    def best_match(_errors: Sequence[ValidationError] | None) -> ValidationError | None:
        return None

from . import cli as cli_module
from genecoder.formats import SequenceBatch
from genecoder.html_report import generate_html_report
from genecoder.metrics import metrics, set_metrics_path
from genecoder.core import metrics as gather_metrics
from genecoder.manifest import generate_manifest
from genecoder.plugin_manager import FEC_REGISTRY, init_plugins
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.synthesis import SynthesisConstraints


@dataclass
class ChannelArgs:
    """Subset of channel options used by bundle configs."""

    simulators: list[str] | None = None
    config: str | None = None
    sub_prob: float | None = None
    ins_prob: float | None = None
    del_prob: float | None = None
    seed: int | None = None
    min_length: int | None = None
    max_length: int | None = None
    max_homopolymer: int | None = None
    parallel: bool = False
    threads: int | None = None
    processes: int | None = None

logger = logging.getLogger(__name__)


def _parse_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _parse_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _load_bundle_schema() -> dict[str, Any]:
    schema_path = (
        Path(__file__).resolve().parents[3]
        / "configs"
        / "schema"
        / "bundle.schema.json"
    )
    with open(schema_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _augment_schema(schema: dict[str, Any]) -> dict[str, Any]:
    schema = copy.deepcopy(schema)
    defs = schema.setdefault("$defs", {})

    fec_choices = set(FEC_REGISTRY.keys()) | {"triple_repeat", "hamming_7_4"}
    fec_prop = defs.get("encode", {}).get("properties", {}).get("fec")
    if isinstance(fec_prop, dict):
        existing = set(fec_prop.get("enum", [])) if isinstance(fec_prop.get("enum"), list) else set()
        values = sorted(existing | fec_choices)
        if values:
            fec_prop["enum"] = values
        else:
            fec_prop.pop("enum", None)

    simulator_choices = set(SIMULATOR_REGISTRY.keys())
    sim_name_def = defs.get("simulatorName")
    if isinstance(sim_name_def, dict):
        existing = set(sim_name_def.get("enum", [])) if isinstance(sim_name_def.get("enum"), list) else set()
        values = sorted(existing | simulator_choices)
        if values:
            sim_name_def["enum"] = values
        else:
            sim_name_def.pop("enum", None)

    return schema


def _format_schema_error(error: ValidationError) -> str:
    params = getattr(error, "params", {}) or {}
    extra = params.get("additionalProperties") if isinstance(params, dict) else None
    if error.validator == "additionalProperties":
        extras: list[str] = []
        if isinstance(extra, list):
            extras = [str(item) for item in extra]
        elif isinstance(error.instance, Mapping):
            instance_keys = {str(k) for k in error.instance}
            schema_props = (
                error.schema.get("properties") if isinstance(error.schema, dict) else {}
            )
            allowed = {str(k) for k in schema_props} if isinstance(schema_props, Mapping) else set()
            extras = sorted(instance_keys - allowed)
        if not extras and "'" in error.message:
            parts = [seg for seg in error.message.split("'") if seg.strip()]
            if parts:
                extras = [parts[0]]

        if not error.path:
            return f"Unknown top-level keys: {', '.join(extras)}"
        section = str(error.path[0]) if error.path else ""
        return f"Unknown {section} options: {', '.join(extras)}"

    if error.validator == "type" and error.validator_value == "object" and error.path:
        section = str(error.path[0])
        return f"{section} section must be a mapping"

    path = "".join(f"[{p!r}]" if isinstance(p, int) else f".{p}" for p in error.path)
    prefix = path.lstrip(".") or "<root>"
    return f"{prefix}: {error.message}"


def _validate_bundle_config(config: Mapping[str, object], config_path: Path) -> None:
    init_plugins()
    schema = _augment_schema(_load_bundle_schema())
    validator = Draft202012Validator(schema)
    error = best_match(validator.iter_errors(config))
    if error is None:
        return

    message = _format_schema_error(error)
    raise ValueError(f"Invalid bundle config at {config_path} ({message})")


def register_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "bundle", help="Manage bundled workflows"
    )
    bundle_sub = parser.add_subparsers(dest="bundle_command", required=True)
    run_parser = bundle_sub.add_parser(
        "run", help="Run encode/decode steps from a YAML config"
    )
    run_parser.add_argument("config", type=str, help="Path to bundle YAML file")
    run_parser.add_argument(
        "--cache-dir",
        type=str,
        default="bundle_runs",
        help="Directory to store bundle outputs",
    )
    run_parser.add_argument(
        "--export-archive",
        type=str,
        help="Path to write a tar.gz archive of the run directory",
    )
    run_parser.add_argument(
        "--author",
        type=str,
        help="Author name to include in summary.json",
    )
    run_parser.add_argument(
        "--description",
        type=str,
        help="Description to include in summary.json",
    )
    run_parser.add_argument(
        "--metrics-path",
        type=str,
        help="Path to the aggregate metrics JSON file",
    )
    run_parser.add_argument(
        "--emit-manifest-report",
        action="store_true",
        help="Generate HTML reports for decoded manifests",
    )
    run_parser.add_argument(
        "--launch-dashboard",
        action="store_true",
        help="Launch the dashboard for the metrics file after the run",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configs and create placeholder outputs without running the pipeline",
    )
    run_parser.set_defaults(func=_handle_run)

    sweep_parser = bundle_sub.add_parser(
        "sweep", help="Run multiple bundle configs with shared cache and metrics"
    )
    sweep_parser.add_argument(
        "configs",
        nargs="+",
        help="YAML bundle configs or glob patterns to run sequentially",
    )
    sweep_parser.add_argument(
        "--cache-dir",
        type=str,
        default="bundle_runs",
        help="Directory to store bundle outputs",
    )
    sweep_parser.add_argument(
        "--metrics-path",
        type=str,
        help="Path to the aggregate metrics JSON file shared across runs",
    )
    sweep_parser.add_argument(
        "--manifest-index",
        type=str,
        help="Path to write a manifest index JSON for dashboard aggregation",
    )
    sweep_parser.add_argument(
        "--export-archive",
        type=str,
        help="Path to write a tar.gz archive of the final run directory",
    )
    sweep_parser.add_argument(
        "--author",
        type=str,
        help="Author name to include in summary.json files",
    )
    sweep_parser.add_argument(
        "--description",
        type=str,
        help="Description to include in summary.json files",
    )
    sweep_parser.add_argument(
        "--emit-manifest-report",
        action="store_true",
        help="Generate HTML reports for decoded manifests",
    )
    sweep_parser.add_argument(
        "--launch-dashboard",
        action="store_true",
        help="Launch the dashboard for the metrics file after the sweep",
    )
    sweep_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configs and create placeholder outputs without running the pipeline",
    )
    sweep_parser.set_defaults(func=_handle_sweep)


def _channel_args(opts: Mapping[str, object]) -> list[str]:
    if not isinstance(opts, dict):
        raise TypeError("simulate section must be a mapping")

    field_names = {f.name for f in fields(ChannelArgs)}
    unknown = set(opts) - field_names
    if unknown:
        raise ValueError(f"Unknown channel options: {', '.join(sorted(unknown))}")

    args = ["channel"]
    data = ChannelArgs(**cast(dict[str, Any], opts))
    for key, value in asdict(data).items():
        if value is None:
            continue
        opt = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                args.append(opt)
        elif isinstance(value, list):
            for v in value:
                args.extend([opt, str(v)])
        else:
            args.extend([opt, str(value)])
    return args


def _simple_args(prefix: str, opts: dict[str, object], allowed: set[str]) -> list[str]:
    if not isinstance(opts, dict):
        raise TypeError(f"{prefix} section must be a mapping")

    unknown = set(opts) - allowed
    if unknown:
        raise ValueError(f"Unknown {prefix} options: {', '.join(sorted(unknown))}")

    args = [prefix]
    for key, value in opts.items():
        if value is None:
            continue
        opt = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                args.append(opt)
        elif isinstance(value, list):
            args.append(opt)
            args.extend([str(v) for v in value])
        else:
            args.extend([opt, str(value)])
    return args


def _run_cli(args_list: list[str]) -> None:
    try:
        cli_module.main(args_list)
    except SystemExit as exc:  # pragma: no cover - passthrough
        if exc.code:
            raise


def _create_archive(
    run_dir: Path,
    archive_path: Path,
    config_hash: str,
    author: str | None = None,
    description: str | None = None,
    batch_metadata: Mapping[str, object] | None = None,
    *,
    config_name: str | None = None,
    channel_profile: str | None = None,
    ecc_type: str | None = None,
    metrics_target: Path | None = None,
) -> None:
    """Create a gzipped tar archive of ``run_dir`` with a summary manifest."""
    _write_summary_file(
        run_dir,
        config_hash,
        batch_metadata=batch_metadata,
        author=author,
        description=description,
        config_name=config_name,
        channel_profile=channel_profile,
        ecc_type=ecc_type,
        metrics_target=metrics_target,
    )

    with tarfile.open(archive_path, "w:gz") as tf:
        tf.add(run_dir, arcname=run_dir.name)
    logger.info("Archive written to %s", archive_path)


def _load_simulated_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _expand_histogram(histogram: Mapping[str, object]) -> list[int]:
    counts: list[int] = []
    for key, value in sorted(histogram.items(), key=lambda item: int(str(item[0]))):
        try:
            cov = int(key)
            repetitions = int(value)
        except (TypeError, ValueError):
            continue
        if repetitions <= 0:
            continue
        counts.extend([cov] * repetitions)
    return counts


def _derive_constraints(
    enc_cfg: Mapping[str, object] | None, sim_cfg: Mapping[str, object] | None
) -> SynthesisConstraints | None:
    """Return synthesis constraints from encoding and simulation configs."""

    params: dict[str, float | int] = {}

    def _apply_int(key: str, raw: object, *, prefer_min: bool = False) -> None:
        val = _parse_int(raw)
        if val is None:
            return
        if prefer_min and key in params:
            try:
                params[key] = min(int(params[key]), val)
            except Exception:
                params[key] = val
        else:
            params[key] = val

    def _apply_float(key: str, raw: object) -> None:
        val = _parse_float(raw)
        if val is not None:
            params[key] = val

    if isinstance(sim_cfg, Mapping):
        synth_cfg = sim_cfg.get("synthesis") if isinstance(sim_cfg, Mapping) else None
        if isinstance(synth_cfg, Mapping):
            _apply_int("min_length", synth_cfg.get("min_length"))
            _apply_int("max_length", synth_cfg.get("max_length"))
            _apply_int("max_homopolymer", synth_cfg.get("max_homopolymer"))
            _apply_float("gc_min", synth_cfg.get("gc_min"))
            _apply_float("gc_max", synth_cfg.get("gc_max"))

    if isinstance(enc_cfg, Mapping):
        _apply_int("min_length", enc_cfg.get("min_length"))
        _apply_int("max_length", enc_cfg.get("max_length"))
        _apply_int("max_homopolymer", enc_cfg.get("max_homopolymer"), prefer_min=True)
        _apply_float("gc_min", enc_cfg.get("gc_min"))
        _apply_float("gc_max", enc_cfg.get("gc_max"))

    if not params:
        return None

    try:
        return SynthesisConstraints(**params)
    except Exception:
        logger.warning("Ignoring invalid synthesis constraints in bundle config")
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


def _write_decoded_metrics(
    original_path: Path,
    simulated_path: Path,
    decoded_path: Path,
    enc_cfg: Mapping[str, object],
    sim_cfg: Mapping[str, object] | None,
    *,
    emit_manifest_report: bool = False,
) -> None:
    constraints = _derive_constraints(enc_cfg, sim_cfg)
    try:
        batch = SequenceBatch.from_fasta(
            simulated_path.read_text(encoding="utf-8")
        )
        sequences = [ol.sequence for ol in batch.oligos] or [batch.primary_sequence()]
    except Exception:
        sequences = [simulated_path.read_text(encoding="utf-8").strip()]
        sequences = [seq for seq in sequences if seq]
        if not sequences:
            sequences = [""]

    manifest_path = simulated_path.with_suffix(".manifest.json")
    manifest_data = _load_simulated_manifest(manifest_path)

    stages_raw = manifest_data.get("stages", [])
    stage_metadata: list[dict[str, Any]] = []
    if isinstance(stages_raw, Sequence):
        for item in stages_raw:
            if isinstance(item, Mapping):
                normalized: dict[str, Any] = {"name": item.get("name", "")}
                if item.get("stage"):
                    normalized["stage"] = item.get("stage")
                params = item.get("parameters")
                if isinstance(params, Mapping):
                    normalized["parameters"] = dict(params)
                opts = item.get("options")
                if isinstance(opts, Sequence) and not isinstance(opts, (str, bytes, bytearray)):
                    normalized["options"] = [str(opt) for opt in opts if str(opt)]
                elif isinstance(opts, str) and opts:
                    normalized["options"] = [opt for opt in opts.split() if opt]
                stage_metadata.append(normalized)

    coverage_info = manifest_data.get("coverage", {})
    histogram_raw = (
        coverage_info.get("histogram", {})
        if isinstance(coverage_info, Mapping)
        else {}
    )
    histogram: dict[str, int] = {}
    if isinstance(histogram_raw, Mapping):
        for key, value in histogram_raw.items():
            try:
                cov = int(str(key))
                cnt = int(value)
            except (TypeError, ValueError):
                continue
            histogram[str(cov)] = histogram.get(str(cov), 0) + max(cnt, 0)

    coverage_counts = _expand_histogram(histogram)
    if not coverage_counts:
        coverage_counts = [1] * len(sequences)

    dropout_flags = [cov <= 0 for cov in coverage_counts]
    if len(dropout_flags) < len(sequences):
        dropout_flags.extend([False] * (len(sequences) - len(dropout_flags)))
    elif len(dropout_flags) > len(sequences):
        dropout_flags = dropout_flags[: len(sequences)]
        coverage_counts = coverage_counts[: len(sequences)]

    dropout_data = manifest_data.get("dropout", {})
    dropout_count = 0
    dropout_fraction = 0.0
    if isinstance(dropout_data, Mapping):
        try:
            dropout_count = int(dropout_data.get("count", 0))
        except (TypeError, ValueError):
            dropout_count = 0
        try:
            dropout_fraction = float(dropout_data.get("fraction", 0.0) or 0.0)
        except (TypeError, ValueError):
            dropout_fraction = 0.0

    synthesis_data = manifest_data.get("synthesis", {})
    synthesis_count = 0
    synthesis_fraction = 0.0
    if isinstance(synthesis_data, Mapping):
        try:
            synthesis_count = int(synthesis_data.get("count", 0))
        except (TypeError, ValueError):
            synthesis_count = 0
        try:
            synthesis_fraction = float(synthesis_data.get("fraction", 0.0) or 0.0)
        except (TypeError, ValueError):
            synthesis_fraction = 0.0

    average_cov = coverage_info.get("average") if isinstance(coverage_info, Mapping) else None
    if average_cov is None:
        average_cov = sum(coverage_counts) / max(1, len(coverage_counts))
    try:
        average_cov_float = float(average_cov)
    except (TypeError, ValueError):
        average_cov_float = 0.0

    total_reads = coverage_info.get("total_reads") if isinstance(coverage_info, Mapping) else None
    try:
        total_reads_int = int(total_reads) if total_reads is not None else sum(coverage_counts)
    except (TypeError, ValueError):
        total_reads_int = sum(coverage_counts)

    original_bytes = original_path.read_bytes()
    decoded_bytes = decoded_path.read_bytes()
    fec = enc_cfg.get("fec") if isinstance(enc_cfg, Mapping) else None
    oligos = sequences if sequences else [""]

    metrics_data = gather_metrics(
        "".join(sequences),
        original_bytes,
        decoded_bytes,
        str(fec) if fec else None,
        coverage=int(round(average_cov_float)),
        constraints=constraints,
        oligos=oligos,
        dropout_flags=dropout_flags,
    )

    constraint_limits = _constraints_limits(constraints)
    if constraint_limits:
        metrics_data.setdefault("constraint_violations", {}).setdefault(
            "limits", constraint_limits
        )

    oligo_metrics = metrics_data.setdefault("oligo_metrics", {})
    oligo_metrics["coverage_counts"] = coverage_counts
    oligo_metrics.setdefault("dropout_flags", dropout_flags)

    channel_config = {}
    pipeline_cfg = {}
    if isinstance(sim_cfg, Mapping):
        pipeline_obj = sim_cfg.get("pipeline")
        if isinstance(pipeline_obj, Mapping):
            pipeline_cfg = dict(pipeline_obj)
        known_fields = {
            key: value
            for key, value in sim_cfg.items()
            if key in {f.name for f in fields(ChannelArgs)}
        }
        if known_fields:
            channel_config = {
                key: value for key, value in known_fields.items() if value is not None
            }

    histogram_str = {key: int(value) for key, value in histogram.items()}

    channel_metrics: dict[str, Any] = {
        "name": "pipeline",
        "dropout": {"count": dropout_count, "fraction": dropout_fraction},
        "coverage": {
            "average": average_cov_float,
            "total_reads": total_reads_int,
            "histogram": histogram_str,
        },
        "synthesis": {
            "count": synthesis_count,
            "fraction": synthesis_fraction,
        },
        "mutation_totals": manifest_data.get("mutation_totals", {}),
        "oligo_count": len(sequences),
    }
    if pipeline_cfg:
        channel_metrics["configuration"] = pipeline_cfg
    if channel_config:
        channel_metrics["parameters"] = channel_config
    if stage_metadata:
        channel_metrics["stages"] = stage_metadata

    sequence_metadata: dict[str, Any] = {
        "sim_dropout_total": str(dropout_count),
        "sim_dropout_fraction": f"{dropout_fraction:.6f}",
        "sim_coverage_histogram": json.dumps(histogram_str),
        "sim_total_reads": str(total_reads_int),
        "sim_average_coverage": f"{average_cov_float:.6f}",
    }
    if stage_metadata:
        sequence_metadata["sim_stages"] = json.dumps(stage_metadata)
    if pipeline_cfg:
        if "dropout_rate" in pipeline_cfg:
            sequence_metadata["sim_dropout_rate"] = str(pipeline_cfg["dropout_rate"])
        if "coverage_distribution" in pipeline_cfg:
            sequence_metadata["sim_coverage_distribution"] = json.dumps(
                pipeline_cfg["coverage_distribution"]
            )
        if "synthesis_loss" in pipeline_cfg:
            sequence_metadata["sim_synthesis_loss"] = str(
                pipeline_cfg["synthesis_loss"]
            )

    if isinstance(sim_cfg, Mapping) and sim_cfg.get("seed") is not None:
        sequence_seed = sim_cfg.get("seed")
    else:
        sequence_seed = None

    sequence_batch_data = {
        "batch_id": original_path.stem,
        "seed": sequence_seed,
        "metadata": sequence_metadata,
    }

    metrics_data["channel"] = channel_metrics
    metrics_data["dropout_count"] = dropout_count
    metrics_data["dropout_fraction"] = dropout_fraction
    metrics_data["sequence_batch"] = sequence_batch_data

    metrics_payload = {"metrics": metrics_data}
    metrics_path = Path(str(decoded_path) + ".json")
    metrics_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")

    manifest_params: dict[str, Any] = {"method": enc_cfg.get("method")}
    if enc_cfg.get("fec"):
        manifest_params["fec"] = enc_cfg.get("fec")
    if channel_metrics:
        manifest_params["channel"] = channel_metrics.get("name")

    manifest = generate_manifest(original_path, manifest_params, metrics_data)
    manifest_output = metrics_path.with_suffix(".manifest.json")
    manifest_output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if emit_manifest_report:
        html_report_path = manifest_output.with_suffix(".html")
        html = generate_html_report(str(manifest_output))
        html_report_path.write_text(html, encoding="utf-8")

def _launch_dashboard_if_requested(launch_dashboard: bool, metrics_override: Path | None) -> None:
    if not launch_dashboard:
        return
    target = metrics_override or metrics.path
    if not target.exists():
        logger.warning(
            "Metrics file %s not found, skipping dashboard launch", target
        )
        return
    _run_cli(["dashboard", str(target)])


def _extract_channel_profile(sim_cfg: Mapping[str, object] | None) -> str | None:
    if not isinstance(sim_cfg, Mapping):
        return None
    pipeline_cfg = sim_cfg.get("pipeline")
    if isinstance(pipeline_cfg, Mapping):
        profile = pipeline_cfg.get("profile") or pipeline_cfg.get("name")
        if profile:
            return str(profile)
    config_path = sim_cfg.get("config")
    if isinstance(config_path, str):
        return config_path
    simulators = sim_cfg.get("simulators")
    if isinstance(simulators, Sequence) and simulators:
        first = simulators[0]
        if isinstance(first, str):
            return first
    return None


def _write_summary_file(
    run_dir: Path,
    config_hash: str,
    *,
    batch_metadata: Mapping[str, object] | None = None,
    author: str | None = None,
    description: str | None = None,
    config_name: str | None = None,
    channel_profile: str | None = None,
    ecc_type: str | None = None,
    metrics_target: Path | None = None,
) -> Path:
    summary = {
        "config_hash": config_hash,
        "timestamp": run_dir.name,
        "files": [
            str(p.relative_to(run_dir)) for p in run_dir.rglob("*") if p.is_file()
        ],
    }
    if batch_metadata:
        summary["sequence_batches"] = batch_metadata
    if author is not None:
        summary["author"] = author
    if description is not None:
        summary["description"] = description
    summary["config_name"] = config_name
    summary["channel_profile"] = channel_profile
    summary["ecc"] = ecc_type
    if metrics_target is not None:
        summary["metrics_path"] = str(metrics_target)

    summary_path = run_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    return summary_path


@dataclass
class BundleRunResult:
    config_path: Path
    config_hash: str
    run_dir: Path
    config_name: str | None
    channel_profile: str | None
    ecc_type: str | None
    summary_path: Path


def _run_single_bundle(
    config_path: Path,
    *,
    cache_dir: Path,
    export_archive: Path | None,
    author: str | None,
    description: str | None,
    emit_manifest_report: bool,
    metrics_override: Path | None,
    launch_dashboard: bool,
    dry_run: bool,
) -> BundleRunResult:
    cache_dir.mkdir(parents=True, exist_ok=True)

    import yaml

    if metrics_override:
        set_metrics_path(metrics_override)

    with open(config_path, "r", encoding="utf-8") as fh:
        try:
            config = yaml.safe_load(fh.read()) or {}
        except yaml.YAMLError as exc:  # pragma: no cover - invalid YAML path
            logger.error("Invalid YAML in %s: %s", config_path, exc)
            raise SystemExit(1)

    if not isinstance(config, dict):
        raise TypeError("Top level YAML must be a mapping")

    _validate_bundle_config(config, config_path)

    allowed_sections = {"encode", "simulate", "decode"}
    unknown_sections = set(config) - allowed_sections
    if unknown_sections:
        raise ValueError(
            f"Unknown top-level keys: {', '.join(sorted(unknown_sections))}"
        )

    config_hash = hashlib.sha256(
        json.dumps(config, sort_keys=True).encode()
    ).hexdigest()
    config_name = config_path.name

    enc_cfg_raw = config.get("encode", {})
    if not isinstance(enc_cfg_raw, dict):
        raise TypeError("encode section must be a mapping")
    enc_cfg = dict(enc_cfg_raw)
    fec_downgraded = False
    if enc_cfg.get("fec") == "reed_solomon" and importlib.util.find_spec("reedsolo") is None:
        logger.warning(
            "reedsolo is unavailable; running bundle encode without Reed-Solomon FEC"
        )
        enc_cfg["fec"] = None
        fec_downgraded = True
    sim_cfg_raw = config.get("simulate")
    if sim_cfg_raw is not None and not isinstance(sim_cfg_raw, dict):
        raise TypeError("simulate section must be a mapping")
    dec_cfg = config.get("decode")
    if dec_cfg is not None and not isinstance(dec_cfg, dict):
        raise TypeError("decode section must be a mapping")

    hash_dir = cache_dir / config_hash
    if hash_dir.exists() and not dry_run:
        logger.info("Cached result found in %s", hash_dir)
        run_dirs = sorted(hash_dir.iterdir())
        if not run_dirs:
            raise RuntimeError(f"Cache directory {hash_dir} is empty")
        run_dir = run_dirs[-1]
        summary_path = _write_summary_file(
            run_dir,
            config_hash,
            author=author,
            description=description,
            config_name=config_name,
            channel_profile=_extract_channel_profile(sim_cfg_raw),
            ecc_type=str(enc_cfg.get("fec")) if enc_cfg.get("fec") else None,
            metrics_target=metrics_override or metrics.path,
        )
        if export_archive:
            _create_archive(
                run_dir,
                export_archive,
                config_hash,
                author,
                description,
                batch_metadata=None,
                config_name=config_name,
                channel_profile=_extract_channel_profile(sim_cfg_raw),
                ecc_type=str(enc_cfg.get("fec")) if enc_cfg.get("fec") else None,
                metrics_target=metrics_override or metrics.path,
            )
        _launch_dashboard_if_requested(launch_dashboard, metrics_override)
        return BundleRunResult(
            config_path=config_path,
            config_hash=config_hash,
            run_dir=run_dir,
            config_name=config_name,
            channel_profile=_extract_channel_profile(sim_cfg_raw),
            ecc_type=str(enc_cfg.get("fec")) if enc_cfg.get("fec") else None,
            summary_path=summary_path,
        )

    constraints = _derive_constraints(enc_cfg, sim_cfg_raw if isinstance(sim_cfg_raw, dict) else None)
    if constraints is not None:
        enc_cfg["gc_min"] = constraints.gc_min
        enc_cfg["gc_max"] = constraints.gc_max
        enc_cfg["max_homopolymer"] = constraints.max_homopolymer

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    run_dir = hash_dir / timestamp
    encoded_dir = run_dir / "encoded"
    simulated_dir = run_dir / "simulated"
    decoded_dir = run_dir / "decoded"
    encoded_dir.mkdir(parents=True, exist_ok=True)
    decoded_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        simulated_dir.mkdir(parents=True, exist_ok=True)
        placeholder_manifest = encoded_dir / "dry_run.manifest.json"
        placeholder_manifest.write_text(
            json.dumps(
                {
                    "config": config_name,
                    "dry_run": True,
                    "config_hash": config_hash,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        decoded_placeholder = decoded_dir / "dry_run.json"
        decoded_placeholder.write_text(
            json.dumps({"config": config_name, "dry_run": True}, indent=2),
            encoding="utf-8",
        )
        metrics_target = metrics_override or metrics.path
        metrics_target.parent.mkdir(parents=True, exist_ok=True)
        if not metrics_target.exists():
            metrics_target.write_text("{}", encoding="utf-8")

        summary_path = _write_summary_file(
            run_dir,
            config_hash,
            author=author,
            description=description,
            config_name=config_name,
            channel_profile=_extract_channel_profile(sim_cfg_raw),
            ecc_type=str(enc_cfg.get("fec")) if enc_cfg.get("fec") else None,
            metrics_target=metrics_override or metrics.path,
        )
        return BundleRunResult(
            config_path=config_path,
            config_hash=config_hash,
            run_dir=run_dir,
            config_name=config_name,
            channel_profile=_extract_channel_profile(sim_cfg_raw),
            ecc_type=str(enc_cfg.get("fec")) if enc_cfg.get("fec") else None,
            summary_path=summary_path,
        )

    enc_args = _simple_args(
        "encode",
        enc_cfg,
        {"input_files", "method", "fec", "gc_min", "gc_max", "max_homopolymer"},
    )
    enc_args += ["--output-dir", str(encoded_dir)]
    _run_cli(enc_args)

    original_inputs = [Path(p) for p in enc_cfg.get("input_files", [])]
    input_files = [encoded_dir / (Path(p).name + ".fasta") for p in enc_cfg.get("input_files", [])]
    batch_summary: dict[str, object] = {}
    for fasta_path in input_files:
        if not fasta_path.exists():
            continue
        try:
            batch = SequenceBatch.from_fasta(fasta_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            logger.warning("Could not parse FASTA batch for %s: %s", fasta_path, exc)
            continue
        payload = {
            "batch_id": batch.batch_id,
            "seed": batch.seed,
            "metadata": batch.metadata,
            "oligos": [
                {
                    "id": ol.oligo_id,
                    "index": ol.index,
                    "seed": ol.seed,
                    "metadata": ol.metadata,
                }
                for ol in batch.oligos
            ],
        }
        metadata_path = fasta_path.with_suffix(fasta_path.suffix + ".batch.json")
        with open(metadata_path, "w", encoding="utf-8") as meta_f:
            json.dump(payload, meta_f, indent=2)
        try:
            rel = fasta_path.relative_to(run_dir)
        except ValueError:
            rel = fasta_path
        batch_summary[str(rel)] = payload

    if batch_summary:
        with open(run_dir / "sequence_batches.json", "w", encoding="utf-8") as fh:
            json.dump(batch_summary, fh, indent=2)

    sim_cfg = sim_cfg_raw if isinstance(sim_cfg_raw, dict) else None
    if fec_downgraded and isinstance(sim_cfg, dict):
        simulators = sim_cfg.get("simulators")
        if isinstance(simulators, list):
            updated: list[object] = []
            for entry in simulators:
                if isinstance(entry, str):
                    name = entry
                    params: dict[str, object] = {"name": name}
                elif isinstance(entry, dict):
                    name = str(entry.get("name", ""))
                    params = dict(entry)
                else:
                    updated.append(entry)
                    continue

                lowered = name.lower()
                if lowered in {"insilicoseq", "illumina_insilicoseq"}:
                    params.setdefault("error_rate", 0.0)
                elif lowered in {"illumina", "illumina_builtin", "illumina_d2sim"}:
                    params.setdefault("substitution_rate", 0.0)
                    params.setdefault("insertion_rate", 0.0)
                    params.setdefault("deletion_rate", 0.0)
                updated.append(params)
            sim_cfg = dict(sim_cfg)
            sim_cfg["simulators"] = updated
    if sim_cfg:
        simulated_dir.mkdir(parents=True, exist_ok=True)
        new_inputs = []
        # When the simulate section contains inline configuration keys (such as
        # pipeline definitions), serialize it to a temporary YAML file for each
        # input and invoke ``channel run`` using that config. This allows bundle
        # configs to reuse the richer channel pipeline syntax.
        if isinstance(sim_cfg, dict) and "config" not in sim_cfg and {
            key
            for key in sim_cfg
            if key not in {f.name for f in fields(ChannelArgs)}
        }:
            try:  # Optional dependency – mirror channel CLI behaviour
                import yaml  # type: ignore
            except Exception:  # pragma: no cover - optional dependency fallback
                from genecoder.plugin_manager import yaml as yaml_module

                if yaml_module is None:  # pragma: no cover - defensive
                    raise

                yaml = yaml_module

            for f in input_files:
                out_f = simulated_dir / f.name
                channel_config = copy.deepcopy(sim_cfg)
                channel_config["input"] = str(f)
                channel_config["output"] = str(out_f)

                with tempfile.NamedTemporaryFile(
                    "w", suffix=".yaml", delete=False, encoding="utf-8"
                ) as tmp:
                    yaml.safe_dump(channel_config, tmp)
                    config_inline_path = Path(tmp.name)

                try:
                    _run_cli(["channel", "run", str(config_inline_path)])
                    new_inputs.append(out_f)
                except ValueError as exc:
                    logger.warning("Channel simulation failed: %s", exc)
                    new_inputs.append(f)
                finally:
                    try:
                        os.unlink(config_inline_path)
                    except FileNotFoundError:  # pragma: no cover - already removed
                        pass
        else:
            sim_args_common = _channel_args(sim_cfg)
            for f in input_files:
                out_f = simulated_dir / f.name
                sim_args = sim_args_common + [
                    "--input-file",
                    str(f),
                    "--output-file",
                    str(out_f),
                ]
                try:
                    _run_cli(sim_args)
                    new_inputs.append(out_f)
                except ValueError as exc:
                    logger.warning("Channel simulation failed: %s", exc)
                    new_inputs.append(f)

        input_files = new_inputs

    if dec_cfg:
        dec_args = _simple_args("decode", dec_cfg, {"method"})
        dec_args += ["--input-files"] + [str(p) for p in input_files]
        dec_args += ["--output-dir", str(decoded_dir)]
        _run_cli(dec_args)

        for original, simulated in zip(original_inputs, input_files):
            decoded_file = decoded_dir / (Path(simulated).stem + "_decoded.bin")
            if decoded_file.exists():
                _write_decoded_metrics(
                    original,
                    Path(simulated),
                    decoded_file,
                    enc_cfg,
                    sim_cfg if isinstance(sim_cfg, dict) else None,
                    emit_manifest_report=emit_manifest_report,
                )

    logger.info("Bundle output written to %s", run_dir)
    summary_path = _write_summary_file(
        run_dir,
        config_hash,
        batch_metadata=batch_summary,
        author=author,
        description=description,
        config_name=config_name,
        channel_profile=_extract_channel_profile(sim_cfg),
        ecc_type=str(enc_cfg.get("fec")) if enc_cfg.get("fec") else None,
        metrics_target=metrics_override or metrics.path,
    )
    if export_archive:
        _create_archive(
            run_dir,
            export_archive,
            config_hash,
            author,
            description,
            batch_summary,
            config_name=config_name,
            channel_profile=_extract_channel_profile(sim_cfg),
            ecc_type=str(enc_cfg.get("fec")) if enc_cfg.get("fec") else None,
            metrics_target=metrics_override or metrics.path,
        )

    metrics.increment("bundle_runs")
    _launch_dashboard_if_requested(launch_dashboard, metrics_override)

    return BundleRunResult(
        config_path=config_path,
        config_hash=config_hash,
        run_dir=run_dir,
        config_name=config_name,
        channel_profile=_extract_channel_profile(sim_cfg),
        ecc_type=str(enc_cfg.get("fec")) if enc_cfg.get("fec") else None,
        summary_path=summary_path,
    )


def _expand_config_patterns(config_patterns: Sequence[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in config_patterns:
        path = Path(pattern)
        if any(ch in pattern for ch in "*?["):
            if path.is_absolute():
                matched = sorted(path.parent.glob(path.name))
            else:
                matched = sorted(Path().glob(pattern))
            paths.extend([p for p in matched if p.is_file()])
        elif path.exists():
            paths.append(path)
    return paths


def _collect_manifest_index(
    results: Sequence[BundleRunResult],
    *,
    manifest_index_path: Path,
) -> None:
    manifest_index_path.parent.mkdir(parents=True, exist_ok=True)
    index_data: dict[str, list[dict[str, object]]] = {"runs": []}
    if manifest_index_path.exists():
        try:
            loaded = json.loads(manifest_index_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("runs"), list):
                index_data = {"runs": list(loaded["runs"])}
        except json.JSONDecodeError:
            logger.warning("Existing manifest index at %s is invalid; regenerating", manifest_index_path)

    new_entries = []
    for res in results:
        encoded_manifests = sorted(res.run_dir.glob("encoded/*.manifest.json"))
        decoded_metrics = sorted(res.run_dir.glob("decoded/*.json"))
        new_entries.append(
            {
                "config_path": str(res.config_path),
                "config_hash": res.config_hash,
                "config_name": res.config_name,
                "run_dir": str(res.run_dir),
                "summary": str(res.summary_path),
                "manifests": [str(p) for p in encoded_manifests],
                "decoded_metrics": [str(p) for p in decoded_metrics],
                "channel_profile": res.channel_profile,
                "ecc": res.ecc_type,
            }
        )

    deduped = [
        entry
        for entry in index_data["runs"]
        if entry.get("config_hash")
        not in {e["config_hash"] for e in new_entries}
    ]
    deduped.extend(new_entries)
    index_data["runs"] = deduped
    manifest_index_path.write_text(json.dumps(index_data, indent=2), encoding="utf-8")


def _handle_run(args: argparse.Namespace) -> None:
    metrics_override: Path | None = Path(args.metrics_path) if args.metrics_path else None
    if metrics_override:
        set_metrics_path(metrics_override)

    _run_single_bundle(
        Path(args.config),
        cache_dir=Path(args.cache_dir),
        export_archive=Path(args.export_archive) if args.export_archive else None,
        author=args.author,
        description=args.description,
        emit_manifest_report=args.emit_manifest_report,
        metrics_override=metrics_override,
        launch_dashboard=args.launch_dashboard,
        dry_run=args.dry_run,
    )


def _handle_sweep(args: argparse.Namespace) -> None:
    metrics_override: Path | None = Path(args.metrics_path) if args.metrics_path else None
    if metrics_override:
        set_metrics_path(metrics_override)

    config_paths = _expand_config_patterns(args.configs)
    if not config_paths:
        raise FileNotFoundError("No bundle configs matched the supplied patterns")

    results: list[BundleRunResult] = []
    for cfg_path in config_paths:
        results.append(
            _run_single_bundle(
                cfg_path,
                cache_dir=Path(args.cache_dir),
                export_archive=Path(args.export_archive) if args.export_archive else None,
                author=args.author,
                description=args.description,
                emit_manifest_report=args.emit_manifest_report,
                metrics_override=metrics_override,
                launch_dashboard=False,
                dry_run=args.dry_run,
            )
        )

    _collect_manifest_index(
        results,
        manifest_index_path=Path(
            args.manifest_index
            if args.manifest_index
            else Path(args.cache_dir) / "manifest_index.json"
        ),
    )

    _launch_dashboard_if_requested(args.launch_dashboard, metrics_override)
