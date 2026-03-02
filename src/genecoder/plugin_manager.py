from __future__ import annotations

import importlib
import subprocess
import urllib.request
from importlib.metadata import entry_points

import genecoder.plugin_runtime as runtime
from .plugin_runtime import discovery as discovery_mod
from .plugin_runtime import installer as installer_mod
from .plugin_runtime.policy import validate_plugin_metadata as _validate_plugin_metadata
from .plugin_runtime.policy import validate_spec as _validate_spec

CODEC_REGISTRY = runtime.CODEC_REGISTRY
FEC_REGISTRY = runtime.FEC_REGISTRY
VISUALIZER_REGISTRY = runtime.VISUALIZER_REGISTRY
SIMULATOR_REGISTRY = runtime.SIMULATOR_REGISTRY
PLUGIN_CATALOG = runtime.PLUGIN_CATALOG
ENTRY_POINT_GROUPS = runtime.ENTRY_POINT_GROUPS
_ENTRY_POINT_METADATA = runtime.ENTRY_POINT_METADATA
compute_checksum = runtime.compute_checksum
yaml = runtime.yaml

register_plugin = runtime.register_plugin
register_codec = runtime.register_codec
register_fec = runtime.register_fec
register_simulator = runtime.register_simulator
register_visualizer = runtime.register_visualizer
install_catalog_plugin = runtime.install_catalog_plugin
generate_plugin_lock = runtime.generate_plugin_lock
_collect_installed_plugins = runtime._collect_installed_plugins
load_registry_mapping = runtime.load_registry_mapping
_verify_catalog_signature = runtime._verify_catalog_signature


def _sync_runtime_hooks() -> None:
    discovery_mod.entry_points = entry_points
    installer_mod.subprocess = subprocess
    installer_mod.urllib.request = urllib.request


def install_registry_plugins(url=None, *, offline=None, allow_network=None) -> None:
    _sync_runtime_hooks()
    runtime.install_registry_plugins(url, offline=offline, allow_network=allow_network)


def load_entry_point_plugins() -> list[str]:
    _sync_runtime_hooks()
    return runtime.load_entry_point_plugins()


def load_plugin_catalog(url: str | None = None) -> None:
    _sync_runtime_hooks()
    runtime.load_plugin_catalog(url)


def load_plugins() -> None:
    _sync_runtime_hooks()
    runtime.load_plugins()


def init_plugins() -> None:
    _sync_runtime_hooks()
    runtime.init_plugins()


def __getattr__(name: str):
    return getattr(runtime, name)


__all__ = [
    "CODEC_REGISTRY",
    "FEC_REGISTRY",
    "VISUALIZER_REGISTRY",
    "SIMULATOR_REGISTRY",
    "PLUGIN_CATALOG",
    "ENTRY_POINT_GROUPS",
    "register_plugin",
    "register_codec",
    "register_fec",
    "register_simulator",
    "register_visualizer",
    "install_registry_plugins",
    "install_catalog_plugin",
    "load_plugins",
    "load_entry_point_plugins",
    "load_plugin_catalog",
    "init_plugins",
    "generate_plugin_lock",
    "_validate_spec",
    "_validate_plugin_metadata",
    "_collect_installed_plugins",
    "_ENTRY_POINT_METADATA",
    "load_registry_mapping",
    "compute_checksum",
    "_verify_catalog_signature",
    "yaml",
    "entry_points",
    "subprocess",
    "urllib",
    "importlib",
]
