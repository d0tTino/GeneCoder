from __future__ import annotations

import importlib
import logging
import os
import pkgutil
import sys
from importlib.metadata import EntryPoints, PackageNotFoundError, entry_points, version as get_pkg_version
from types import ModuleType
from typing import Any, Callable, cast

from .descriptors import PluginDescriptor, PluginLifecycleState
from .policy import validate_plugin_metadata
from .registry import RUNTIME_REGISTRY, register_lazy_placeholder

logger = logging.getLogger(__name__)

ENTRY_POINT_METADATA: dict[str, dict[str, Any]] = {}


def _entry_point_version(entry_point: object) -> str:
    dist = getattr(entry_point, "dist", None)
    version = getattr(dist, "version", None)
    if version:
        return str(version)
    module_name = getattr(entry_point, "module", "")
    for root in [module_name.split(".")[0], getattr(entry_point, "value", "").split(":", 1)[0].split(".")[0]]:
        if root:
            try:
                return get_pkg_version(root)
            except PackageNotFoundError:
                pass
    return ""


def _record_entry_point_metadata(entry_name: str, kind: str, entry_point: object) -> None:
    meta = ENTRY_POINT_METADATA.setdefault(entry_name, {})
    meta.setdefault("entry_name", entry_name)
    meta.setdefault("metadata_name", meta.get("metadata_name") or entry_name)
    if not meta.get("version"):
        version = _entry_point_version(entry_point)
        if version:
            meta["version"] = version
    interfaces = meta.setdefault("interfaces", set())
    interfaces.add(kind)
    module_name = getattr(entry_point, "module", None) or str(getattr(entry_point, "value", "")).split(":", 1)[0]
    if module_name:
        meta.setdefault("module", module_name)
    meta.setdefault("entry_point", entry_point)


def _update_entry_point_metadata(entry_name: str, module: ModuleType) -> None:
    try:
        meta = validate_plugin_metadata(getattr(module, "PLUGIN_METADATA", None))
    except Exception as exc:
        cached = ENTRY_POINT_METADATA.setdefault(entry_name, {})
        cached["invalid"] = True
        cached["invalid_metadata"] = True
        logger.warning("Incompatible plugin %s: %s", entry_name, exc)
        return
    cached = ENTRY_POINT_METADATA.setdefault(entry_name, {})
    cached.update({
        "entry_name": entry_name,
        "metadata_name": meta["name"],
        "version": meta["version"],
        "interfaces": set(meta["interfaces"]),
        "license": meta["license"],
    })


def _load_entry_point_module(entry_point: object, registrar: Callable[..., object], kind: str, entry_name: str) -> None:
    module = entry_point.load()
    _update_entry_point_metadata(entry_name, module)
    register = getattr(module, "register", None)
    if callable(register):
        register(registrar)


def load_entry_point_plugins(*, offline: bool, registrars: dict[str, tuple[Callable[..., Any], str]]) -> tuple[list[str], list[PluginDescriptor]]:
    failures: list[str] = []
    descriptors: list[PluginDescriptor] = []
    for loaders in RUNTIME_REGISTRY.entry_point_loaders.values():
        loaders.clear()

    for group, (registrar, kind) in registrars.items():
        try:
            entries = entry_points(group=group)
        except TypeError:
            eps = entry_points()
            if hasattr(eps, "select"):
                entries = eps.select(group=group)
            elif isinstance(eps, dict):
                entries = eps.get(group, EntryPoints())
            else:
                entries = [ep for ep in eps if getattr(ep, "group", None) == group]

        seen: set[str] = set()
        for ep in entries:
            entry_name = str(getattr(ep, "name", ""))
            entry_value = str(getattr(ep, "value", entry_name))
            entry_key = entry_name or entry_value
            if not entry_key:
                failures.append(f"{kind}:unknown")
                continue
            seen.add(entry_key)
            _record_entry_point_metadata(entry_key, kind, ep)
            descriptor = PluginDescriptor(name=entry_key, kind=kind, source=f"entry_point:{group}", version=_entry_point_version(ep))
            descriptors.append(descriptor)

            if offline:
                RUNTIME_REGISTRY.entry_point_loaders[kind][entry_key] = (
                    lambda entry=ep, reg=registrar, k=kind, name=entry_value: _load_entry_point_module(entry, reg, k, name)
                )
                register_lazy_placeholder(kind, entry_key)
                descriptor.state = PluginLifecycleState.DISCOVERED
                continue
            try:
                _load_entry_point_module(ep, registrar, kind, entry_value)
                descriptor.state = PluginLifecycleState.LOADED
            except (ImportError, ModuleNotFoundError):
                descriptor.state = PluginLifecycleState.FAILED
                failures.append(f"{kind}:{entry_value}")

        for meta in ENTRY_POINT_METADATA.values():
            interfaces = meta.get("interfaces")
            if isinstance(interfaces, set) and kind in interfaces and meta.get("entry_name") not in seen:
                interfaces.discard(kind)

    return failures, descriptors


def collect_installed_plugins(existing_catalog: dict[str, dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], list[str], list[PluginDescriptor]]:
    ENTRY_POINT_METADATA.clear()
    catalog: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    descriptors: list[PluginDescriptor] = []
    offline = bool(os.getenv("GENECODER_OFFLINE"))

    groups = {
        "genecoder.plugins": "codec",
        "genecoder.fec": "FEC",
        "genecoder.simulators": "simulator",
        "genecoder.visualizers": "visualizer",
    }
    for group, kind in groups.items():
        try:
            entries = entry_points(group=group)
        except TypeError:
            eps = entry_points()
            if hasattr(eps, "select"):
                entries = eps.select(group=group)
            elif isinstance(eps, dict):
                entries = eps.get(group, EntryPoints())
            else:
                entries = [ep for ep in eps if getattr(ep, "group", None) == group]
        for ep in entries:
            entry_name = str(getattr(ep, "value", getattr(ep, "name", "")))
            if entry_name:
                _record_entry_point_metadata(entry_name, kind, ep)

    for entry_name, cached in list(ENTRY_POINT_METADATA.items()):
        if cached.get("invalid_metadata"):
            continue
        if cached.get("metadata_name") and cached.get("metadata_name") != cached.get("entry_name"):
            continue
        module_name = cached.get("module")
        entry_point = cached.get("entry_point")
        module = sys.modules.get(str(module_name)) if module_name else None
        if module is None and entry_point is not None and not offline:
            try:
                module = cast(ModuleType, entry_point.load())
            except Exception as exc:
                failures.append(f"entry_point:{entry_name}")
                logger.warning("Failed to import entry point metadata for %s: %s", entry_name, exc)
                continue
        if module is not None:
            _update_entry_point_metadata(entry_name, module)

    for cached in ENTRY_POINT_METADATA.values():
        if cached.get("invalid"):
            continue
        entry_name = str(cached.get("entry_name") or "")
        plugin_name = str(cached.get("metadata_name") or entry_name)
        if cached.get("invalid_metadata") or not plugin_name:
            continue
        interfaces = {str(i) for i in (cached.get("interfaces") or set())}
        version = str(cached.get("version") or "")
        license_value = str(cached.get("license") or "")
        catalog[plugin_name] = {"version": version, "interfaces": sorted(interfaces), "license": license_value}
        descriptors.append(PluginDescriptor(name=plugin_name, kind="metadata", source="entry_point", version=version, license=license_value, state=PluginLifecycleState.VALIDATED))

    try:
        import plugins as local_pkg
    except ModuleNotFoundError:
        local_pkg = None

    modules: list[ModuleType] = []
    if local_pkg is not None:
        modules.append(local_pkg)
        if hasattr(local_pkg, "__path__"):
            for _, module_name, _ in pkgutil.iter_modules(local_pkg.__path__):
                try:
                    modules.append(importlib.import_module(f"plugins.{module_name}"))
                except Exception as exc:
                    src = f"local:{module_name}"
                    failures.append(src)
                    logger.warning("Failed to import %s: %s", src, exc)
    for mod in modules:
        src = getattr(mod, "__name__", "local")
        try:
            meta = validate_plugin_metadata(getattr(mod, "PLUGIN_METADATA", None))
        except Exception as exc:
            failures.append(src)
            logger.warning("Incompatible plugin %s: %s", src, exc)
            continue
        name = meta["name"]
        if name in catalog or name in existing_catalog:
            failures.append(src)
            logger.warning("Duplicate plugin name %s from %s", name, src)
            continue
        catalog[name] = {"version": meta["version"], "interfaces": meta["interfaces"], "license": meta["license"]}
        descriptors.append(PluginDescriptor(name=name, kind="metadata", source=src, version=meta["version"], license=meta["license"], state=PluginLifecycleState.VALIDATED))
    return catalog, failures, descriptors
