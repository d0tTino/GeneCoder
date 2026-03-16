from __future__ import annotations

import argparse
import logging

import genecoder.plugin_runtime as plugins
from genecoder.app.ui_service import UIService

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

    reg_parser = plugin_sub.add_parser(
        "install-registry", help="Install packages from the configured registry"
    )
    reg_parser.add_argument(
        "--allow-registry",
        action="store_true",
        help="Allow downloading and installing packages from the registry",
    )
    reg_parser.add_argument(
        "--offline",
        action="store_true",
        help="Read registry from a local file and disable network access",
    )
    reg_parser.set_defaults(func=_handle_install_registry)

    disable_parser = plugin_sub.add_parser(
        "disable", help="Disable a loaded plugin by name"
    )
    disable_parser.add_argument("name", help="Plugin name")
    disable_parser.set_defaults(func=_handle_disable)

    rollback_parser = plugin_sub.add_parser(
        "rollback", help="Mark a plugin as rolled back by name"
    )
    rollback_parser.add_argument("name", help="Plugin name")
    rollback_parser.set_defaults(func=_handle_rollback)


def _handle_list(args: argparse.Namespace) -> None:
    plugin_catalog = UIService().list_plugins().get("plugins", {})
    if not plugin_catalog:
        logger.info("No plugin catalog available")
        return
    for name, meta in plugin_catalog.items():
        version = meta.get("version", "")
        desc = meta.get("description", "")
        display = f"{name}" + (f"=={version}" if version else "")
        if desc:
            display += f" - {desc}"
        print(display)


def _handle_install(args: argparse.Namespace) -> None:
    try:
        plugins.install_catalog_plugin(args.name)
    except KeyError:
        logger.error("Unknown plugin: %s", args.name)
        raise SystemExit(1)


def _handle_install_registry(args: argparse.Namespace) -> None:
    if not args.allow_registry:
        logger.error("Registry installation requires --allow-registry")
        raise SystemExit(1)

    plugins.install_registry_plugins(offline=args.offline)


def _handle_disable(args: argparse.Namespace) -> None:
    try:
        state = plugins.disable_plugin(args.name)
    except KeyError:
        logger.error("Unknown plugin: %s", args.name)
        raise SystemExit(1)
    logger.info("Plugin %s transitioned to %s", args.name, state.value)


def _handle_rollback(args: argparse.Namespace) -> None:
    try:
        state = plugins.rollback_plugin(args.name)
    except KeyError:
        logger.error("Unknown plugin: %s", args.name)
        raise SystemExit(1)
    logger.info("Plugin %s transitioned to %s", args.name, state.value)
