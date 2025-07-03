from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, cast

from genecoder import report as report_module


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
    fec_parser.add_argument("--plot", type=Path, help="Write PNG plot of results")
    fec_parser.set_defaults(func=_handle_fec)


def _parse_results(text: str, fmt: str) -> list[dict[str, float | str]]:
    if fmt == "json":
        return cast(List[Dict[str, float | str]], json.loads(text))
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


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
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode)
    results_text = proc.stdout
    if args.plot:
        results = _parse_results(results_text, args.format)
        buf = report_module.plot_fec_benchmark(results)
        with open(args.plot, "wb") as fh:
            fh.write(buf.getvalue())
        buf.close()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(results_text)
    else:
        sys.stdout.write(results_text)
