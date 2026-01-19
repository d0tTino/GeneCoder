from __future__ import annotations

import argparse
import logging


logger = logging.getLogger(__name__)


def register_subcommand(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "dashboard", help="Launch the Streamlit dashboard"
    )
    parser.add_argument(
        "results_json",
        nargs="+",
        help="Path(s) to results JSON file(s)",
    )
    parser.set_defaults(func=_handle_command)


def _handle_command(args: argparse.Namespace) -> None:
    try:
        from genecoder.dashboard_streamlit import launch

        launch(*args.results_json)
    except (ImportError, RuntimeError) as exc:
        logger.warning(
            "Streamlit dashboard unavailable (%s). Install streamlit or use the HTML report workflow instead.",
            exc,
        )
