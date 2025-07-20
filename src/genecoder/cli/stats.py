from __future__ import annotations

import argparse

from genecoder.metrics import get_metrics, oligos_per_week
from typing import TypeAlias, cast


def register_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("stats", help="Show usage metrics including simulation counts")
    parser.set_defaults(func=_handle_command)


def _handle_command(_: argparse.Namespace) -> None:
    data = collect_stats()
    for k, v in data.items():
        print(f"{k}: {v}")


StatsData: TypeAlias = dict[str, int | list[str] | dict[str, int]]


def collect_stats() -> StatsData:
    """Return current usage metrics."""

    data: StatsData = cast(StatsData, get_metrics())


    data["oligos_per_week"] = oligos_per_week()
    return data
