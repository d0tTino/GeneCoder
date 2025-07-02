from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
import yaml  # type: ignore

from . import cli as cli_module

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
    run_parser.set_defaults(func=_handle_run)


def _normalize_args(prefix: str, opts: dict[str, object]) -> list[str]:
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


def _handle_run(args: argparse.Namespace) -> None:
    with open(args.config, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}

    config_hash = hashlib.sha256(
        json.dumps(config, sort_keys=True).encode()
    ).hexdigest()
    hash_dir = Path(args.cache_dir) / config_hash
    if hash_dir.exists():
        logger.info("Cached result found in %s", hash_dir)
        return

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    run_dir = hash_dir / timestamp
    encoded_dir = run_dir / "encoded"
    simulated_dir = run_dir / "simulated"
    decoded_dir = run_dir / "decoded"
    encoded_dir.mkdir(parents=True, exist_ok=True)
    decoded_dir.mkdir(parents=True, exist_ok=True)

    enc_cfg = config.get("encode", {})
    enc_args = _normalize_args("encode", enc_cfg)
    enc_args += ["--output-dir", str(encoded_dir)]
    _run_cli(enc_args)

    input_files = [encoded_dir / (Path(p).name + ".fasta") for p in enc_cfg.get("input_files", [])]

    sim_cfg = config.get("simulator")
    if sim_cfg:
        simulated_dir.mkdir(parents=True, exist_ok=True)
        sim_args_common = _normalize_args("simulate-errors", sim_cfg)
        new_inputs = []
        for f in input_files:
            out_f = simulated_dir / f.name
            sim_args = sim_args_common + ["--input-file", str(f), "--output-file", str(out_f)]
            _run_cli(sim_args)
            new_inputs.append(out_f)
        input_files = new_inputs

    dec_cfg = config.get("decode")
    if dec_cfg:
        dec_args = _normalize_args("decode", dec_cfg)
        dec_args += ["--input-files"] + [str(p) for p in input_files]
        dec_args += ["--output-dir", str(decoded_dir)]
        _run_cli(dec_args)

    logger.info("Bundle output written to %s", run_dir)
