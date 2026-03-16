from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TypeAlias, cast

from genecoder.bundle_metrics import aggregate_metrics
from genecoder.metrics import get_metrics, oligos_per_week


def register_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("stats", help="Show usage metrics including simulation counts")
    parser.set_defaults(func=_handle_command)

    stats_subparsers = parser.add_subparsers(dest="stats_command")

    bundle_parser = stats_subparsers.add_parser(
        "bundle", help="Aggregate metrics from cached bundle runs"
    )
    bundle_parser.add_argument(
        "--runs",
        required=True,
        type=Path,
        help="Path to bundle cache directory containing manifest files",
    )
    bundle_parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON file to write aggregated metrics",
    )
    bundle_parser.set_defaults(func=_handle_bundle_command)


def _handle_command(_: argparse.Namespace) -> None:
    data = collect_stats()
    for k, v in data.items():
        print(f"{k}: {v}")


def _handle_bundle_command(args: argparse.Namespace) -> None:
    metrics = aggregate_metrics(args.runs)
    output = json.dumps(metrics, indent=2)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    print(
        f"cost_per_recovered_bit (avg): {float(metrics.get('avg_cost_per_recovered_bit', 0.0)):.6f}",
        file=sys.stderr,
    )
    print(
        "reads_per_successful_decode (avg): "
        f"{float(metrics.get('avg_reads_per_successful_decode', 0.0)):.2f}",
        file=sys.stderr,
    )
    print(
        f"redundancy_cost_ratio (avg): {float(metrics.get('avg_redundancy_cost_ratio', 0.0)):.4f}",
        file=sys.stderr,
    )


StatsData: TypeAlias = dict[str, int | list[str] | dict[str, int]]


def collect_stats() -> StatsData:
    """Return current usage metrics."""

    data: StatsData = cast(StatsData, get_metrics())


    data["oligos_per_week"] = oligos_per_week()
    return data
