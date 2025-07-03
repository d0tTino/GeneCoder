from __future__ import annotations

import argparse
import logging
import subprocess
import sys

from genecoder import plugins

logger = logging.getLogger(__name__)


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
    subprocess.check_call([sys.executable, "-m", "pip", "install", spec])

