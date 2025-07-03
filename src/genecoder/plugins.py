from __future__ import annotations

from typing import Callable, Dict, Any, Iterable
from types import ModuleType
import os
import sys
import subprocess
import urllib.request
from urllib.parse import urlparse
import importlib
import hashlib

_yaml: Any
try:  # pragma: no cover - import is trivial
    _yaml = importlib.import_module("yaml")
except Exception:  # pragma: no cover - optional dependency
    _yaml = None
yaml: Any | None = _yaml

from .channels.base import BaseChannel
from importlib.metadata import entry_points, EntryPoints
import logging
import pkgutil

from .simulators import SIMULATOR_REGISTRY, register_simulator as _register_simulator
from .security import compute_checksum

logger = logging.getLogger(__name__)

CODEC_REGISTRY: Dict[str, Dict[str, Callable[..., Any]]] = {}
FEC_REGISTRY: Dict[str, Dict[str, Callable[..., Any]]] = {}
PLUGIN_CATALOG: Dict[str, Dict[str, str]] = {}


def register_codec(name: str, encode: Callable[..., Any], decode: Callable[..., Any]) -> None:
    """Register a codec implementation under ``name``."""
    CODEC_REGISTRY[name] = {"encode": encode, "decode": decode}


def register_fec(name: str, encode: Callable[..., Any], decode: Callable[..., Any]) -> None:
    """Register a FEC backend under ``name``."""
    FEC_REGISTRY[name] = {"encode": encode, "decode": decode}


def register_simulator(name: str, channel: BaseChannel) -> None:
    """Register a read simulator under ``name``."""
    _register_simulator(name, channel)


def _verify_catalog_signature(data: bytes, signature: str) -> bool:
    """Return True if ``data`` matches ``signature``.

    The default implementation uses a SHA256 hex digest. This is a minimal
    check intended mainly for testing and does not provide real security.
    """

    try:
        digest = hashlib.sha256(data).hexdigest()
    except Exception:
        return False
    return digest == signature


def _install_registry_plugins(url: str) -> None:
    """Install plugin packages listed in a YAML registry at ``url``."""

    if yaml is None:  # pragma: no cover - optional dependency missing
        logger.warning("YAML support unavailable, skipping plugin registry %s", url)
        return

    if urlparse(url).scheme != "https":
        logger.warning("Insecure plugin registry URL %s", url)
        return

    try:
        with urllib.request.urlopen(url) as response:
            data = yaml.safe_load(response.read()) or {}
    except Exception as exc:  # pragma: no cover - network error path
        logger.warning("Failed to fetch plugin registry %s: %s", url, exc)
        return

    for entry in data.get("packages", []):
        if isinstance(entry, dict):
            spec = str(entry.get("spec") or entry.get("package") or entry.get("url") or "")
            checksum = str(entry.get("checksum", ""))
        else:
            logger.warning("Missing checksum for plugin entry %s", entry)
            continue

        if not spec or not checksum:
            logger.warning("Incomplete plugin entry in registry: %s", entry)
            continue

        if compute_checksum(spec.encode()) != checksum:
            logger.warning("Checksum mismatch for plugin %s", spec)
            continue

        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", spec])
        except Exception as exc:  # pragma: no cover - install error path
            logger.warning("Failed to install plugin %s from registry: %s", spec, exc)


def _fetch_catalog(url: str) -> None:
    """Fetch plugin catalogue from ``url`` and store in ``PLUGIN_CATALOG``."""

    if yaml is None:  # pragma: no cover - optional dependency missing
        logger.warning("YAML support unavailable, skipping plugin catalog %s", url)
        return

    try:
        with urllib.request.urlopen(url) as response:
            raw = response.read()
        data = yaml.safe_load(raw) or {}
    except Exception as exc:  # pragma: no cover - network error path
        logger.warning("Failed to fetch plugin catalog %s: %s", url, exc)
        return

    sig = data.get("signature")
    if sig:
        try:
            if not _verify_catalog_signature(raw, str(sig)):
                logger.warning("Invalid catalog signature for %s", url)
                return
        except Exception as exc:  # pragma: no cover - signature error path
            logger.warning("Invalid catalog signature for %s: %s", url, exc)
            return

    PLUGIN_CATALOG.clear()
    for entry in data.get("plugins", []):
        name = str(entry.get("name", ""))
        if not name:
            continue
        PLUGIN_CATALOG[name] = {
            "version": str(entry.get("version", "")),
            "url": str(entry.get("url", "")),
            "description": str(entry.get("description", "")),
            "checksum": str(entry.get("checksum", "")),
        }


def _load_and_register(
    items: Iterable[Any],
    registrar: Callable[..., Any],
    kind: str,
    failures: list[str] | None = None,
) -> None:
    """Load ``items`` and call ``register`` on each."""

    for item in items:
        name = getattr(item, "value", getattr(item, "__name__", str(item)))
        try:
            module = (
                item
                if isinstance(item, ModuleType)
                else item.load()
                if hasattr(item, "load")
                else importlib.import_module(name)
            )
        except Exception:  # pragma: no cover - error path
            if failures is not None:
                failures.append(f"{kind}:{name}")
            else:
                logger.warning("Failed to import %s plugin %s", kind, name)
            continue
        register = getattr(module, "register", None)
        if callable(register):
            register(registrar)


def load_plugins() -> None:
    """Load plugins and fetch catalog entries."""

    CODEC_REGISTRY.clear()
    FEC_REGISTRY.clear()
    SIMULATOR_REGISTRY.clear()

    # First load built-in plugin modules
    builtin = importlib.import_module("genecoder.builtin_plugins")
    if hasattr(builtin, "register_builtin_plugins"):
        builtin.register_builtin_plugins()

    registry_url = os.getenv("GENECODER_PLUGIN_REGISTRY_URL")
    if registry_url:
        _install_registry_plugins(registry_url)

    catalog_url = os.getenv("GENECODER_PLUGIN_CATALOG_URL")
    if catalog_url:
        _fetch_catalog(catalog_url)
    else:
        PLUGIN_CATALOG.clear()

    failures: list[str] = []

    groups: dict[str, tuple[Callable[..., Any], str]] = {
        "genecoder.plugins": (register_codec, "codec"),
        "genecoder.fec": (register_fec, "FEC"),
        "genecoder.simulators": (register_simulator, "simulator"),
    }
    for group, (registrar, kind) in groups.items():
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
        _load_and_register(entries, registrar, kind, failures)

    # Also load plugins from a local ``plugins`` package if present
    try:
        import plugins
    except ModuleNotFoundError:
        plugins = None
    if plugins is not None:
        if hasattr(plugins, "__path__"):
            for _, module_name, _ in pkgutil.iter_modules(plugins.__path__):
                try:
                    module = importlib.import_module(f"plugins.{module_name}")
                except Exception:  # pragma: no cover - error path
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
        register = getattr(plugins, "register", None)
        if callable(register):
            register(register_codec)
        register_f = getattr(plugins, "register_fec", None)
        if callable(register_f):
            register_f(register_fec)
        register_s = getattr(plugins, "register_simulator", None)
        if callable(register_s):
            register_s(register_simulator)

    if failures:
        logger.warning("Failed to import plugins: %s", ", ".join(failures))

