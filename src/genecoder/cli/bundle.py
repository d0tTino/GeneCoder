from __future__ import annotations

import argparse
import hashlib
import json
import logging
import tarfile
from datetime import datetime
from pathlib import Path

from . import cli as cli_module

_ALLOWED_CACHE: dict[str, set[str]] | None = None


def _get_allowed(command: str) -> set[str]:
    global _ALLOWED_CACHE
    if _ALLOWED_CACHE is None:
        parser = cli_module.build_parser()
        subparsers = next(
            a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
        )
        _ALLOWED_CACHE = {}
        for name in ("encode", "channel", "decode"):
            sub = subparsers.choices[name]
            allowed = {
                act.dest
                for act in sub._actions
                if act.option_strings and act.dest != "help"
            }
            _ALLOWED_CACHE[name] = allowed
    return _ALLOWED_CACHE[command]

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
    run_parser.set_defaults(func=_handle_run)


def _normalize_args(prefix: str, opts: dict[str, object]) -> list[str]:
    if not isinstance(opts, dict):
        raise TypeError(f"{prefix} section must be a mapping")

    allowed = _get_allowed(prefix)
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
        elif isinstance(value, (int, float, str)):
            args.extend([opt, str(value)])
        else:
            raise TypeError(
                f"Invalid type for {prefix}.{key}: {type(value).__name__}"
            )
    return args


def _run_cli(args_list: list[str]) -> None:
    try:
        cli_module.main(args_list)
    except SystemExit as exc:  # pragma: no cover - passthrough
        if exc.code:
            raise


def _create_archive(run_dir: Path, archive_path: Path, config_hash: str) -> None:
    """Create a gzipped tar archive of ``run_dir`` with a summary manifest."""
    summary = {
        "config_hash": config_hash,
        "timestamp": run_dir.name,
        "files": [str(p.relative_to(run_dir)) for p in run_dir.rglob("*") if p.is_file()],
    }
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
                _create_archive(run_dirs[-1], Path(args.export_archive), config_hash)
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
    enc_args = _normalize_args("encode", enc_cfg)
    enc_args += ["--output-dir", str(encoded_dir)]
    _run_cli(enc_args)

    input_files = [encoded_dir / (Path(p).name + ".fasta") for p in enc_cfg.get("input_files", [])]

    sim_cfg = config.get("simulate")
    if sim_cfg is not None and not isinstance(sim_cfg, dict):
        raise TypeError("simulate section must be a mapping")
    if sim_cfg:
        simulated_dir.mkdir(parents=True, exist_ok=True)
        sim_args_common = _normalize_args("channel", sim_cfg)
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
        dec_args = _normalize_args("decode", dec_cfg)
        dec_args += ["--input-files"] + [str(p) for p in input_files]
        dec_args += ["--output-dir", str(decoded_dir)]
        _run_cli(dec_args)

    logger.info("Bundle output written to %s", run_dir)
    if args.export_archive:
        _create_archive(run_dir, Path(args.export_archive), config_hash)
