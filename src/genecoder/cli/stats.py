from __future__ import annotations

import argparse

from genecoder.metrics import get_metrics


def register_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("stats", help="Show usage metrics")
    parser.set_defaults(func=_handle_command)


def _handle_command(_: argparse.Namespace) -> None:
    metrics = get_metrics()
    for k, v in metrics.items():
        print(f"{k}: {v}")
