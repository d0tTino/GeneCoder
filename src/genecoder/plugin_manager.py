from __future__ import annotations

from types import ModuleType
from typing import Any

import base64
import importlib
import json
import logging
import os
import pkgutil
import subprocess
import urllib.request
from pathlib import Path

from . import plugin_security
from importlib.metadata import entry_points

from .plugin_runtime import discovery as discovery_mod
from .plugin_runtime import installer as installer_mod
from .plugin_runtime.discovery import (
    ENTRY_POINT_METADATA as _ENTRY_POINT_METADATA,
    collect_installed_plugins,
    load_entry_point_plugins as _load_entry_point_plugins,
)
from .plugin_runtime.descriptors import PluginDescriptor
from .plugin_runtime.installer import (
    PLUGIN_LOCK,
    PipPluginInstaller,
    fetch_catalog,
    install_registry_plugins as _install_registry_plugins,
    load_registry_mapping,
    render_plugin_lock,
)
from .plugin_runtime.policy import (
    validate_plugin_metadata as _validate_plugin_metadata,
    validate_spec as _validate_spec,
)
from .plugin_runtime.registry import (
    CODEC_REGISTRY,
    FEC_REGISTRY,
    VISUALIZER_REGISTRY,
    register_codec,
    register_fec,
    register_simulator,
    register_visualizer,
)
from .simulators import SIMULATOR_REGISTRY

logger = logging.getLogger(__name__)

PLUGIN_CATALOG: dict[str, dict[str, Any]] = {}

yaml: ModuleType | None
try:
    import yaml as yaml_module
except Exception:
    yaml = None
else:
    yaml = yaml_module

compute_checksum = plugin_security.compute_checksum


class _CompatInstaller(PipPluginInstaller):
    pass


def install_registry_plugins(
    url: str | os.PathLike[str] | None = None,
    *,
    offline: bool | None = None,
    allow_network: bool | None = None,
) -> None:
    global yaml
    yaml_module = yaml
    if yaml_module is None:
        try:
            import yaml as yaml_module_real
        except Exception:
            logger.warning("YAML support unavailable; skipping registry %s", url)
            return
        yaml = yaml_module_real
        yaml_module = yaml_module_real

    installer_mod.subprocess = subprocess
    installer_mod.urllib.request = urllib.request
    descriptors = _install_registry_plugins(
        url,
        offline=offline,
        allow_network=allow_network,
        yaml_module=yaml_module,
        installer=_CompatInstaller(),
    )
    PLUGIN_LOCK.clear()
    PLUGIN_LOCK.extend(d.as_lock_entry() for d in sorted(descriptors, key=lambda d: (d.name, d.version, d.source)))



def _collect_installed_plugins() -> tuple[dict[str, dict[str, Any]], list[str]]:
    discovery_mod.entry_points = entry_points
    catalog, failures, _ = collect_installed_plugins(PLUGIN_CATALOG)
    return catalog, failures


def load_builtin_plugins() -> None:
    CODEC_REGISTRY.clear()
    FEC_REGISTRY.clear()
    VISUALIZER_REGISTRY.clear()
    SIMULATOR_REGISTRY.clear()
    builtin = importlib.import_module("genecoder.builtin_plugins")
    if hasattr(builtin, "register_builtin_plugins"):
        builtin.register_builtin_plugins()


def load_entry_point_plugins() -> list[str]:
    offline = bool(os.getenv("GENECODER_OFFLINE"))
    groups = {
        "genecoder.plugins": (register_codec, "codec"),
        "genecoder.fec": (register_fec, "FEC"),
        "genecoder.simulators": (register_simulator, "simulator"),
        "genecoder.visualizers": (register_visualizer, "visualizer"),
    }
    discovery_mod.entry_points = entry_points
    failures, _ = _load_entry_point_plugins(offline=offline, registrars=groups)
    return failures


def load_local_plugins() -> list[str]:
    failures: list[str] = []
    try:
        import plugins
    except ModuleNotFoundError:
        return failures

    if hasattr(plugins, "__path__"):
        for _, module_name, _ in pkgutil.iter_modules(plugins.__path__):
            try:
                module = importlib.import_module(f"plugins.{module_name}")
            except Exception:
                failures.append(f"local:{module_name}")
                continue
            metadata = getattr(module, "PLUGIN_METADATA", None)
            if metadata is not None:
                try:
                    _validate_plugin_metadata(metadata)
                except Exception:
                    failures.append(f"local:{module_name}")
                    continue
            register = getattr(module, "register", None)
            if callable(register):
                register(register_codec)
            register_f = getattr(module, "register_fec", None)
            if callable(register_f):
                register_f(register_fec)
            register_s = getattr(module, "register_simulator", None)
            if callable(register_s):
                register_s(register_simulator)
            register_v = getattr(module, "register_visualizer", None)
            if callable(register_v):
                register_v(register_visualizer)

    metadata = getattr(plugins, "PLUGIN_METADATA", None)
    if metadata is not None:
        try:
            _validate_plugin_metadata(metadata)
        except Exception:
            failures.append("local:plugins")
            return failures

    register = getattr(plugins, "register", None)
    if callable(register):
        register(register_codec)
    register_f = getattr(plugins, "register_fec", None)
    if callable(register_f):
        register_f(register_fec)
    register_s = getattr(plugins, "register_simulator", None)
    if callable(register_s):
        register_s(register_simulator)
    register_v = getattr(plugins, "register_visualizer", None)
    if callable(register_v):
        register_v(register_visualizer)
    return failures



def _verify_catalog_signature(data: bytes, signature_b64: str, *, padding_scheme: str | None = None) -> bool:
    key_path = os.getenv("GENECODER_CATALOG_PUBLIC_KEY")
    if not key_path:
        return False
    try:
        public_key = Path(key_path).read_bytes()
        signature = base64.b64decode(signature_b64, validate=True)
    except Exception:
        return False
    try:
        compute_checksum(data, signature=signature, public_key=public_key, padding_scheme=padding_scheme or "pkcs1")
    except Exception:
        return False
    return True


def load_plugin_catalog(url: str | None = None) -> None:
    if url is None:
        url = os.getenv("GENECODER_PLUGIN_CATALOG_URL")
    catalog: dict[str, dict[str, Any]] = {}
    offline = bool(os.getenv("GENECODER_OFFLINE"))
    allow_network = bool(os.getenv("GENECODER_ALLOW_NETWORK"))
    network_ok = allow_network and not offline

    if url:
        raw = b""
        if (url.startswith("http://") or url.startswith("https://")) and not network_ok:
            logger.info("Network access disabled; skipped remote catalog %s", url)
        else:
            try:
                raw = fetch_catalog(url, allow_network=network_ok)
            except Exception as exc:
                logger.warning("Failed to fetch plugin catalog %s: %s", url, exc)

        if raw:
            try:
                data = json.loads(raw.decode("utf-8"))
            except Exception:
                if yaml is None:
                    data = {}
                else:
                    try:
                        data = yaml.safe_load(raw) or {}
                    except Exception:
                        data = {}
            if isinstance(data, dict):
                signature = data.get("signature")
                scheme = data.get("signature_scheme") or data.get("scheme")
                if signature and not _verify_catalog_signature(raw, signature, padding_scheme=scheme):
                    logger.warning("Invalid catalog signature for %s", url)
                else:
                    plugins_data = data.get("plugins", data.get("entries", {}))
                    if isinstance(plugins_data, list):
                        for entry in plugins_data:
                            if isinstance(entry, dict) and "name" in entry:
                                catalog[str(entry["name"])] = {k: v for k, v in entry.items() if k != "name"}
                    elif isinstance(plugins_data, dict):
                        for name, meta in plugins_data.items():
                            if isinstance(meta, dict):
                                catalog[str(name)] = dict(meta)

    discovered, failures = _collect_installed_plugins()
    for name, meta in discovered.items():
        catalog.setdefault(name, meta)

    PLUGIN_CATALOG.clear()
    PLUGIN_CATALOG.update(catalog)
    if failures:
        logger.warning("Failed to load plugin metadata: %s", ", ".join(failures))


def generate_plugin_lock() -> str:
    descriptors: list[PluginDescriptor] = []
    for item in PLUGIN_LOCK:
        descriptors.append(
            PluginDescriptor(
                name=item.get("name", ""),
                kind="package",
                source=item.get("source", ""),
                version=item.get("version", ""),
                checksum=item.get("checksum") or None,
                signature=item.get("signature") or None,
            )
        )
    return render_plugin_lock(descriptors)


def load_plugins() -> None:
    load_builtin_plugins()
    failures = load_entry_point_plugins()
    failures.extend(load_local_plugins())
    load_plugin_catalog()
    if failures:
        logger.warning("Failed to import plugins: %s", ", ".join(failures))


_initialized = False


def init_plugins() -> None:
    global _initialized
    if _initialized:
        return
    try:
        load_plugins()
    except Exception as exc:
        logger.warning("Failed to load plugins: %s", exc)
    _initialized = True


__all__ = [
    "CODEC_REGISTRY",
    "FEC_REGISTRY",
    "VISUALIZER_REGISTRY",
    "SIMULATOR_REGISTRY",
    "PLUGIN_CATALOG",
    "register_codec",
    "register_fec",
    "register_simulator",
    "register_visualizer",
    "install_registry_plugins",
    "load_plugins",
    "load_entry_point_plugins",
    "init_plugins",
    "_validate_spec",
    "_validate_plugin_metadata",
    "_collect_installed_plugins",
    "_ENTRY_POINT_METADATA",
    "load_registry_mapping",
]
