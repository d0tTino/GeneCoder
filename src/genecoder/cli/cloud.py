from __future__ import annotations

import argparse
import base64
import tempfile
import zipfile
from pathlib import Path



def register_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("cloud", help="Interact with cloud workers")
    cloud_sub = parser.add_subparsers(dest="cloud_command", required=True)
    submit = cloud_sub.add_parser("submit", help="Submit a bundle to a remote worker")
    submit.add_argument("bundle", type=str, help="Path to bundle YAML file")
    submit.add_argument(
        "--server",
        type=str,
        default="https://localhost:8000",
        help="Worker base URL",
    )
    submit.add_argument("--token", type=str, help="Bearer token for authentication")
    submit.add_argument(
        "--async",
        dest="use_async",
        action="store_true",
        help="Use asynchronous submission",
    )
    submit.set_defaults(func=_handle_submit)


def _handle_submit(args: argparse.Namespace) -> None:
    import warnings
    import yaml
    import asyncio
    from genecoder.cloud import CloudClient, AsyncCloudClient

    if not args.server.startswith("https://"):
        warnings.warn("Using a non-HTTPS server URL", stacklevel=2)
    bundle_path = Path(args.bundle)
    with open(bundle_path, "r", encoding="utf-8") as fh:
        bundle_data = fh.read()
        cfg = yaml.safe_load(bundle_data) or {}
    input_files = [Path(p) for p in cfg.get("encode", {}).get("input_files", [])]

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / "bundle.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr(bundle_path.name, bundle_data)
            for f in input_files:
                zf.write(f, arcname=f.name)
        archive_b64 = base64.b64encode(archive_path.read_bytes()).decode("utf-8")

    if getattr(args, "use_async", False):
        async def _run() -> None:
            async with AsyncCloudClient(args.server, args.token) as client:
                jid = await client.submit("bundle", {"archive": archive_b64})
                print(jid)

        asyncio.run(_run())
    else:
        with CloudClient(args.server, args.token) as client:
            job_id = client.submit("bundle", {"archive": archive_b64})
        print(job_id)
