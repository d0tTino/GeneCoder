from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, cast

from genecoder import report as report_module
from genecoder.results.schema import RUN_SCHEMA_VERSION


_DATA_SIZE = 1_000_000
_ERROR_PROB = 0.01


def register_subcommand(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("benchmark", help="Run benchmark suites")
    bench_sub = parser.add_subparsers(dest="benchmark_cmd", required=True)
    fec_parser = bench_sub.add_parser(
        "fec", help="Benchmark forward error correction back-ends"
    )
    fec_parser.add_argument("--format", choices=["csv", "json"], default="csv")
    fec_parser.add_argument("--output", "-o", type=Path)
    fec_parser.add_argument("--size", type=int, default=_DATA_SIZE)
    fec_parser.add_argument("--error-prob", type=float, default=_ERROR_PROB)
    fec_parser.add_argument(
        "--redundancy",
        type=int,
        nargs="+",
        default=[0],
        help="Redundancy levels to test",
    )
    fec_parser.add_argument("--plot", type=Path, help="Write PNG plot of results")
    fec_parser.set_defaults(func=_handle_fec)


def _parse_results(text: str, fmt: str) -> list[dict[str, float | str]]:
    if fmt == "json":
        return cast(List[Dict[str, float | str]], json.loads(text))
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _to_canonical_artifact(results: list[dict[str, float | str]]) -> dict[str, object]:
    return {
        "schema_version": RUN_SCHEMA_VERSION,
        "source_format": "benchmark_fec",
        "run_id": "benchmark-fec",
        "profiles": {"encoding": None, "simulation": None, "decode": None},
        "seeds": {"global": None, "encode": None, "simulate": None, "decode": None},
        "runtime": {"total_seconds": None, "encode_seconds": None, "simulate_seconds": None, "decode_seconds": None},
        "stages": {"encode": {"metrics": {}}, "simulate": {"metrics": {}}, "decode": {"metrics": {}}},
        "outcome": {"metrics": {"benchmark": results}},
    }


def _handle_fec(args: argparse.Namespace) -> None:
    script = Path(__file__).resolve().parents[3] / "benchmarks" / "fec_bench.py"
    cmd = [
        sys.executable,
        str(script),
        "--format",
        args.format,
        "--size",
        str(args.size),
        "--error-prob",
        str(args.error_prob),
    ]
    for r in args.redundancy:
        cmd.extend(["--redundancy", str(r)])
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(Path(__file__).resolve().parents[3] / "src"), env.get("PYTHONPATH", "")] 
    )
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode)
    results_text = proc.stdout
    results = _parse_results(results_text, args.format)
    artifact = _to_canonical_artifact(results)
    if args.plot:
        if any("redundancy" in r for r in results):
            buf = report_module.plot_fec_success(results)
        else:
            buf = report_module.plot_fec_benchmark(results)
        with open(args.plot, "wb") as fh:
            fh.write(buf.getvalue())
        buf.close()
    payload = json.dumps(artifact, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(payload)
    else:
        sys.stdout.write(payload)
