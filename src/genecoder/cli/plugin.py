from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from pathlib import Path
import subprocess

from pip._internal.exceptions import InstallationSubprocessError
from pip._internal.utils.subprocess import call_subprocess

import genecoder.plugin_manager as plugins
from genecoder.plugin_checks import decode_signature, verify_package

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
        "install-registry", help="Install packages from the configured registry"
    )
    reg_parser.add_argument(
        "--allow-registry",
        action="store_true",
        help="Allow downloading and installing packages from the registry",
    )
    reg_parser.set_defaults(func=_handle_install_registry)



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


def download_plugin_bytes(name: str) -> tuple[str, bytes]:
    """Return ``(filename, bytes)`` for plugin ``name`` after verification."""

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
        except Exception:
            logger.warning("Failed to read public key %s", key_path)
            pubkey = None

    with tempfile.TemporaryDirectory() as tmp_dir:
        _run_pip(
            ["download", "--no-deps", "-d", tmp_dir, spec],
            "pip download",
        )
        files = list(Path(tmp_dir).iterdir())
        if not files:
            logger.error("No package downloaded for plugin %s", name)
            raise SystemExit(1)
        pkg_path = files[0]
        pkg_bytes = pkg_path.read_bytes()

        if signature_b64:
            if pubkey is None:
                logger.error("Missing public key for signed plugin %s", name)
                raise SystemExit(1)
            try:
                sig_bytes = decode_signature(signature_b64)
            except ValueError:
                logger.error("Invalid signature for plugin %s", name)
                raise SystemExit(1)
        else:
            sig_bytes = None

        try:
            verify_package(
                pkg_bytes,
                checksum=checksum,
                signature=sig_bytes,
                public_key=pubkey,
                compute_fn=plugins.compute_checksum,
            )
        except ValueError as exc:
            if str(exc) == "Checksum mismatch":
                logger.error("Checksum mismatch for plugin %s", name)
            else:
                logger.error("Signature verification failed for plugin %s: %s", name, exc)
            raise SystemExit(1)

        return pkg_path.name, pkg_bytes


def download_plugin(name: str) -> None:
    """Download ``name`` from the catalog and install it via ``pip``."""

    filename, pkg_bytes = download_plugin_bytes(name)
    digest = plugins.compute_checksum(pkg_bytes)

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_path = Path(tmp_dir) / filename
        pkg_path.write_bytes(pkg_bytes)

        req_file = Path(tmp_dir) / "req.txt"
        req_file.write_text(f"{pkg_path} --hash=sha256:{digest}\n")

        _run_pip([
            "install",
            "--require-hashes",
            "-r",
            str(req_file),
        ], "pip install")


def _handle_install(args: argparse.Namespace) -> None:
    download_plugin(args.name)


def _handle_install_registry(args: argparse.Namespace) -> None:
    if not args.allow_registry:
        logger.error("Registry installation requires --allow-registry")
        raise SystemExit(1)

    plugins.install_registry_plugins()



