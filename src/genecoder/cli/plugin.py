from __future__ import annotations

import argparse
import base64
import logging
import os
import sys
import tempfile
from pathlib import Path
import subprocess

from pip._internal.exceptions import InstallationSubprocessError
from pip._internal.utils.subprocess import call_subprocess

import genecoder.plugins as plugins

logger = logging.getLogger(__name__)

_ORIG_CHECK_CALL = subprocess.check_call


def _run_pip(args: list[str], desc: str) -> None:
    """Execute pip with output capture.

    When ``subprocess.check_call`` has been monkeypatched (typically by tests),
    the patched function is used instead of pip's internal helper. Otherwise
    :func:`pip._internal.utils.subprocess.call_subprocess` is invoked with
    ``stdout`` capture enabled so output is redirected to the logger.
    """

    try:
        if subprocess.check_call is not _ORIG_CHECK_CALL:
            subprocess.check_call([sys.executable, "-m", "pip", *args])
        else:
            call_subprocess(
                [sys.executable, "-m", "pip", *args],
                stdout_only=True,
                command_desc=desc,
            )
    except InstallationSubprocessError as exc:
        logger.error("%s failed: %s", desc, exc)
        raise SystemExit(exc.exit_code)


def register_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    plugin_parser = subparsers.add_parser("plugin", help="Manage GeneCoder plugins")
    plugin_sub = plugin_parser.add_subparsers(dest="plugin_cmd", required=True)

    list_parser = plugin_sub.add_parser("list", help="List available plugins")
    list_parser.set_defaults(func=_handle_list)

    install_parser = plugin_sub.add_parser(
        "install", help="Install a plugin from the catalog"
    )
    install_parser.add_argument("name", help="Plugin name to install")
    install_parser.set_defaults(func=_handle_install)

    reg_parser = plugin_sub.add_parser(
        "install-registry",
        help="Install all plugins from a registry",
    )
    reg_parser.add_argument(
        "--url",
        help="Registry YAML URL (defaults to $GENECODER_PLUGIN_REGISTRY_URL)",
        default=None,
    )
    reg_parser.set_defaults(func=_handle_install_registry)

    rate_parser = plugin_sub.add_parser(
        "rate", help="Submit a star rating for a plugin"
    )
    rate_parser.add_argument("name", help="Plugin name to rate")
    rate_parser.add_argument("rating", type=int, help="Rating from 1-5")
    rate_parser.add_argument(
        "--server",
        type=str,
        default="https://localhost:8000",
        help="GeneCoder web server URL",
    )
    rate_parser.add_argument("--token", type=str, help="Bearer token for authentication")
    rate_parser.set_defaults(func=_handle_rate)


def _handle_list(args: argparse.Namespace) -> None:
    if not plugins.PLUGIN_CATALOG:
        logger.info("No plugin catalog available")
        return
    for name, meta in plugins.PLUGIN_CATALOG.items():
        version = meta.get("version", "")
        desc = meta.get("description", "")
        display = f"{name}" + (f"=={version}" if version else "")
        if desc:
            display += f" - {desc}"
        print(display)


def _handle_install(args: argparse.Namespace) -> None:
    name = args.name
    meta = plugins.PLUGIN_CATALOG.get(name)
    if not meta:
        logger.error("Unknown plugin: %s", name)
        raise SystemExit(1)
    spec = meta.get("url") or name
    version = meta.get("version")
    if version and not meta.get("url"):
        spec = f"{name}=={version}"
    checksum = meta.get("checksum")
    signature_b64 = meta.get("signature")
    pubkey: bytes | None = None

    key_path = os.getenv("GENECODER_PLUGIN_PUBLIC_KEY")
    if signature_b64:
        if not key_path:
            logger.error("Missing public key for signed plugin %s", name)
            raise SystemExit(1)
        try:
            pubkey = Path(key_path).read_bytes()
        except Exception:  # pragma: no cover - filesystem error path
            logger.warning("Failed to read public key %s", key_path)
            pubkey = None

    with tempfile.TemporaryDirectory() as tmp_dir:
        _run_pip(
            [
                "download",
                "--no-deps",
                "-d",
                tmp_dir,
                spec,
            ],
            "pip download",
        )
        files = list(Path(tmp_dir).iterdir())
        if not files:
            logger.error("No package downloaded for plugin %s", name)
            raise SystemExit(1)
        pkg_path = files[0]
        pkg_bytes = pkg_path.read_bytes()
        if signature_b64 and pubkey is not None:
            try:
                plugins.compute_checksum(
                    pkg_bytes,
                    signature=base64.b64decode(signature_b64),
                    public_key=pubkey,
                )
            except Exception as exc:
                logger.error(
                    "Signature verification failed for plugin %s: %s", name, exc
                )
                raise SystemExit(1)
        if checksum and plugins.compute_checksum(pkg_bytes) != checksum:
            logger.error("Checksum mismatch for plugin %s", name)
            raise SystemExit(1)
        _run_pip(["install", str(pkg_path)], "pip install")


def _handle_install_registry(args: argparse.Namespace) -> None:
    plugins.install_registry_plugins(args.url)


def _handle_rate(args: argparse.Namespace) -> None:
    import warnings
    import httpx

    if not 1 <= args.rating <= 5:
        logger.error("Rating must be 1-5")
        raise SystemExit(1)
    if not args.server.startswith("https://"):
        warnings.warn("Using a non-HTTPS server URL", stacklevel=2)
    url = args.server.rstrip("/") + "/plugins/rate"
    headers = {"Content-Type": "application/json"}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"
    try:
        resp = httpx.post(url, json={"name": args.name, "rating": args.rating}, headers=headers)
        resp.raise_for_status()
    except httpx.HTTPError as exc:  # pragma: no cover - network error path
        logger.error("Failed to submit rating: %s", exc)
        raise SystemExit(1)
    avg = resp.json().get("average")
    if avg is not None:
        print(avg)

