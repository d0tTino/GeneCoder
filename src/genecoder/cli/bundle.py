from __future__ import annotations

import argparse
import hashlib
import json
import logging
import tarfile
from datetime import datetime
from pathlib import Path

from dataclasses import dataclass, fields, asdict

from . import cli as cli_module
from genecoder.metrics import metrics


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
    mpi: bool = False
    mpi_workers: int | None = None

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


def _channel_args(opts: dict[str, object]) -> list[str]:
    if not isinstance(opts, dict):
        raise TypeError("simulate section must be a mapping")

    field_names = {f.name for f in fields(ChannelArgs)}
    unknown = set(opts) - field_names
    if unknown:
        raise ValueError(f"Unknown channel options: {', '.join(sorted(unknown))}")

    args = ["channel"]
    data = ChannelArgs(**opts)
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
) -> None:
    """Create a gzipped tar archive of ``run_dir`` with a summary manifest."""
    summary = {
        "config_hash": config_hash,
        "timestamp": run_dir.name,
        "files": [str(p.relative_to(run_dir)) for p in run_dir.rglob("*") if p.is_file()],
    }
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


def _handle_run(args: argparse.Namespace) -> None:
    import yaml

    with open(args.config, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}

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
    enc_args = _simple_args("encode", enc_cfg, {"input_files", "method"})
    enc_args += ["--output-dir", str(encoded_dir)]
    _run_cli(enc_args)

    input_files = [encoded_dir / (Path(p).name + ".fasta") for p in enc_cfg.get("input_files", [])]

    sim_cfg = config.get("simulate")
    if sim_cfg is not None and not isinstance(sim_cfg, dict):
        raise TypeError("simulate section must be a mapping")
    if sim_cfg:
        simulated_dir.mkdir(parents=True, exist_ok=True)
        sim_args_common = _channel_args(sim_cfg)
        new_inputs = []
        for f in input_files:
            out_f = simulated_dir / f.name
            sim_args = sim_args_common + ["--input-file", str(f), "--output-file", str(out_f)]
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

    logger.info("Bundle output written to %s", run_dir)
    if args.export_archive:
        _create_archive(
            run_dir,
            Path(args.export_archive),
            config_hash,
            args.author,
            args.description,
        )

    metrics.increment("bundle_runs")
