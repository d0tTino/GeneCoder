from __future__ import annotations

import argparse

from genecoder.metrics import get_metrics, oligos_per_week


def register_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("stats", help="Show usage metrics including simulation counts")
    parser.set_defaults(func=_handle_command)


def _handle_command(_: argparse.Namespace) -> None:
    data = collect_stats()
    for k, v in data.items():
        print(f"{k}: {v}")


def collect_stats() -> dict[str, object]:
    """Return current usage metrics."""

    data: dict[str, object] = get_metrics()
    data["oligos_per_week"] = oligos_per_week()
    return data
