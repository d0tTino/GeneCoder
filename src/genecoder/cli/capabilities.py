from __future__ import annotations

import argparse
import json

from genecoder.config import get_capability_manifest


def register_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "capabilities",
        help="Show runtime capability flags shared by the API and web UI",
    )
    parser.add_argument("--json", action="store_true", help="Render the capability manifest as JSON")
    parser.set_defaults(func=_handle_capabilities)


def _handle_capabilities(args: argparse.Namespace) -> None:
    manifest = get_capability_manifest()
    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return

    print(f"execution_mode: {manifest['execution_mode']}")
    print(f"queue_backend: {manifest['queue_backend']}")
    if manifest['supports_async_jobs']:
        print(f"async_job_mode: {manifest['async_job_mode']}")
    if manifest['remote_worker']:
        print('remote_worker: enabled')
