from __future__ import annotations

import argparse
from pathlib import Path

from genecoder.data_service import fetch_profile, DEFAULT_BASE_URL


def register_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("data", help="Manage datasets")
    data_sub = parser.add_subparsers(dest="data_cmd", required=True)

    fetch_p = data_sub.add_parser("fetch", help="Download an error profile")
    fetch_p.add_argument("profile", help="Profile name to download")
    fetch_p.add_argument("--url", default=DEFAULT_BASE_URL, help="Base URL")
    fetch_p.add_argument("--cache-dir", type=str, help="Cache directory")
    fetch_p.add_argument("--refresh", action="store_true", help="Re-download even if cached")
    fetch_p.set_defaults(func=_handle_fetch)


def _handle_fetch(args: argparse.Namespace) -> None:
    cache_dir = Path(args.cache_dir) if args.cache_dir else None
    path = fetch_profile(args.profile, base_url=args.url, cache_dir=cache_dir, refresh=args.refresh)
    print(path)
