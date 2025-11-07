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
from typing import Any, Mapping, cast

from . import cli as cli_module
from genecoder.formats import SequenceBatch
from genecoder.metrics import metrics
from genecoder.core import metrics as gather_metrics
from genecoder.manifest import generate_manifest


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
    run_parser.set_defaults(func=_handle_run)


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
) -> None:
    """Create a gzipped tar archive of ``run_dir`` with a summary manifest."""
    summary = {
        "config_hash": config_hash,
        "timestamp": run_dir.name,
        "files": [str(p.relative_to(run_dir)) for p in run_dir.rglob("*") if p.is_file()],
    }
    if batch_metadata:
        summary["sequence_batches"] = batch_metadata
    if author is not None:
        summary["author"] = author
    if description is not None:
        summary["description"] = description
    summary_path = run_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

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


def _write_decoded_metrics(
    original_path: Path,
    simulated_path: Path,
    decoded_path: Path,
    enc_cfg: Mapping[str, object],
    sim_cfg: Mapping[str, object] | None,
) -> None:
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
        oligos=oligos,
        dropout_flags=dropout_flags,
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

    sequence_metadata: dict[str, Any] = {
        "sim_dropout_total": str(dropout_count),
        "sim_dropout_fraction": f"{dropout_fraction:.6f}",
        "sim_coverage_histogram": json.dumps(histogram_str),
        "sim_total_reads": str(total_reads_int),
        "sim_average_coverage": f"{average_cov_float:.6f}",
    }
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

def _handle_run(args: argparse.Namespace) -> None:
    import yaml

    with open(args.config, "r", encoding="utf-8") as fh:
        try:
            config = yaml.safe_load(fh) or {}
        except yaml.YAMLError as exc:  # pragma: no cover - invalid YAML path
            logger.error("Invalid YAML in %s: %s", args.config, exc)
            raise SystemExit(1)

    if not isinstance(config, dict):
        raise TypeError("Top level YAML must be a mapping")

    allowed_sections = {"encode", "simulate", "decode"}
    unknown_sections = set(config) - allowed_sections
    if unknown_sections:
        raise ValueError(
            f"Unknown top-level keys: {', '.join(sorted(unknown_sections))}"
        )

    config_hash = hashlib.sha256(
        json.dumps(config, sort_keys=True).encode()
    ).hexdigest()
    hash_dir = Path(args.cache_dir) / config_hash
    if hash_dir.exists():
        logger.info("Cached result found in %s", hash_dir)
        if args.export_archive:
            run_dirs = sorted(hash_dir.iterdir())
            if run_dirs:
                _create_archive(
                    run_dirs[-1],
                    Path(args.export_archive),
                    config_hash,
                    args.author,
                    args.description,
                    batch_metadata=None,
                )
        return

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    run_dir = hash_dir / timestamp
    encoded_dir = run_dir / "encoded"
    simulated_dir = run_dir / "simulated"
    decoded_dir = run_dir / "decoded"
    encoded_dir.mkdir(parents=True, exist_ok=True)
    decoded_dir.mkdir(parents=True, exist_ok=True)

    enc_cfg = config.get("encode", {})
    if not isinstance(enc_cfg, dict):
        raise TypeError("encode section must be a mapping")
    enc_args = _simple_args("encode", enc_cfg, {"input_files", "method", "fec"})
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

    sim_cfg = config.get("simulate")
    if sim_cfg is not None and not isinstance(sim_cfg, dict):
        raise TypeError("simulate section must be a mapping")
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
                    config_path = Path(tmp.name)

                try:
                    _run_cli(["channel", "run", str(config_path)])
                finally:
                    try:
                        os.unlink(config_path)
                    except FileNotFoundError:  # pragma: no cover - already removed
                        pass

                new_inputs.append(out_f)
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
                _run_cli(sim_args)
                new_inputs.append(out_f)

        input_files = new_inputs

    dec_cfg = config.get("decode")
    if dec_cfg is not None and not isinstance(dec_cfg, dict):
        raise TypeError("decode section must be a mapping")
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
                )

    logger.info("Bundle output written to %s", run_dir)
    if args.export_archive:
        _create_archive(
            run_dir,
            Path(args.export_archive),
            config_hash,
            args.author,
            args.description,
            batch_summary,
        )

    metrics.increment("bundle_runs")
