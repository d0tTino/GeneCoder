from __future__ import annotations

import base64
import importlib
import json
import logging
import os
from pathlib import Path
from types import ModuleType
from typing import Any

from genecoder import plugin_security

from .discovery import ENTRY_POINT_METADATA, collect_installed_plugins, load_entry_point_plugins as _load_entry_point_plugins, load_local_plugins as _load_local_plugins
from .entry_points import ENTRY_POINT_GROUPS, entry_point_registrars
from .installer import PLUGIN_LOCK, PipPluginInstaller, fetch_catalog, install_plugin_spec, install_registry_plugins as _install_registry_plugins, load_registry_mapping, render_plugin_lock
from .registry import CODEC_REGISTRY, FEC_REGISTRY, VISUALIZER_REGISTRY, register_codec, register_fec, register_plugin, register_simulator, register_visualizer
from genecoder.simulators import SIMULATOR_REGISTRY

logger = logging.getLogger(__name__)

PLUGIN_CATALOG: dict[str, dict[str, Any]] = {}

_initialized = False

yaml: ModuleType | None
try:
    import yaml as yaml_module
except Exception:
    yaml = None
else:
    yaml = yaml_module

compute_checksum = plugin_security.compute_checksum


def _yaml_module_or_none() -> ModuleType | None:
    global yaml
    if yaml is not None:
        return yaml
    try:
        import yaml as yaml_module_real
    except Exception:
        return None
    yaml = yaml_module_real
    return yaml_module_real


def install_registry_plugins(
    url: str | os.PathLike[str] | None = None,
    *,
    offline: bool | None = None,
    allow_network: bool | None = None,
) -> None:
    yaml_module = _yaml_module_or_none()
    if yaml_module is None:
        logger.warning("YAML support unavailable; skipping registry %s", url)
        return
    descriptors = _install_registry_plugins(
        url,
        offline=offline,
        allow_network=allow_network,
        yaml_module=yaml_module,
        installer=PipPluginInstaller(),
    )
    PLUGIN_LOCK.clear()
    PLUGIN_LOCK.extend(d.as_lock_entry() for d in sorted(descriptors, key=lambda d: (d.name, d.version, d.source)))


def install_catalog_plugin(name: str) -> None:
    meta = PLUGIN_CATALOG.get(name)
    if not meta:
        raise KeyError(name)
    spec = str(meta.get("url") or name)
    version = meta.get("version")
    if version and not meta.get("url"):
        spec = f"{name}=={version}"
    offline = bool(os.getenv("GENECODER_OFFLINE"))
    allow_network = bool(os.getenv("GENECODER_ALLOW_NETWORK"))
    network_ok = allow_network and not offline
    checksum = meta.get("checksum")
    signature = meta.get("signature")
    if not isinstance(checksum, str) or not isinstance(signature, str):
        raise ValueError("Signed metadata and checksum are required")
    install_plugin_spec(
        spec,
        checksum=checksum,
        signature=signature,
        allow_network=network_ok,
        installer=PipPluginInstaller(),
    )


def _collect_installed_plugins() -> tuple[dict[str, dict[str, Any]], list[str]]:
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
    failures, _ = _load_entry_point_plugins(
        offline=bool(os.getenv("GENECODER_OFFLINE")),
        registrars=entry_point_registrars(
            register_codec=register_codec,
            register_fec=register_fec,
            register_simulator=register_simulator,
            register_visualizer=register_visualizer,
        ),
    )
    return failures


def load_local_plugins() -> list[str]:
    return _load_local_plugins(
        registrars={
            "codec": register_codec,
            "fec": register_fec,
            "simulator": register_simulator,
            "visualizer": register_visualizer,
        }
    )


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
            logger.info("offline: skipped remote catalog %s", url)
        else:
            try:
                raw = fetch_catalog(url, allow_network=network_ok)
            except Exception as exc:
                logger.warning("Failed to fetch plugin catalog %s: %s", url, exc)

        if raw:
            try:
                data = json.loads(raw.decode("utf-8"))
            except Exception:
                yaml_module = _yaml_module_or_none()
                if yaml_module is None:
                    data = {}
                else:
                    try:
                        data = yaml_module.safe_load(raw) or {}
                    except Exception:
                        data = {}
            if isinstance(data, dict):
                signature = data.get("signature")
                scheme = data.get("signature_scheme") or data.get("scheme")
                if signature and not _verify_catalog_signature(raw, str(signature), padding_scheme=str(scheme) if scheme else None):
                    logger.warning("Invalid catalog signature for %s", url)
                else:
                    plugins_data = data.get("plugins", data.get("entries", {}))
                    if isinstance(plugins_data, list):
                        for entry in plugins_data:
                            if isinstance(entry, dict) and "name" in entry:
                                catalog[str(entry["name"])] = {k: v for k, v in entry.items() if k != "name"}
                    elif isinstance(plugins_data, dict):
                        for pname, meta in plugins_data.items():
                            if isinstance(meta, dict):
                                catalog[str(pname)] = dict(meta)

    discovered, failures = _collect_installed_plugins()
    for pname, meta in discovered.items():
        catalog.setdefault(pname, meta)

    PLUGIN_CATALOG.clear()
    PLUGIN_CATALOG.update(catalog)
    if failures:
        logger.warning("Failed to load plugin metadata: %s", ", ".join(failures))


def generate_plugin_lock() -> str:
    from .descriptors import PluginDescriptor

    descriptors = [
        PluginDescriptor(
            name=item.get("name", ""),
            kind="package",
            source=item.get("source", ""),
            version=item.get("version", ""),
            checksum=item.get("checksum") or None,
            signature=item.get("signature") or None,
        )
        for item in PLUGIN_LOCK
    ]
    return render_plugin_lock(descriptors)


def load_plugins() -> None:
    load_builtin_plugins()
    failures = load_entry_point_plugins()
    failures.extend(load_local_plugins())
    load_plugin_catalog()
    if failures:
        logger.warning("Failed to import plugins: %s", ", ".join(failures))


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
    "ENTRY_POINT_METADATA",
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
    "init_plugins",
    "generate_plugin_lock",
    "load_plugin_catalog",
    "load_registry_mapping",
    "compute_checksum",
]
