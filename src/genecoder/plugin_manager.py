from __future__ import annotations

from typing import Callable, Dict, Any, Iterable
from types import ModuleType

import os
import sys
import subprocess
import urllib.request
from pathlib import Path
import importlib

yaml: ModuleType | None
try:  # optional dependency
    import yaml as yaml_module
except Exception:  # pragma: no cover - optional
    yaml = None
else:
    yaml = yaml_module


from importlib.metadata import entry_points, EntryPoints
import logging
import pkgutil

from .simulators import SIMULATOR_REGISTRY, register_simulator as _register_simulator
from .plugin_security import compute_checksum as _compute_checksum
import base64


logger = logging.getLogger(__name__)

CODEC_REGISTRY: Dict[str, Dict[str, Callable[..., Any]]] = {}
FEC_REGISTRY: Dict[str, Dict[str, Callable[..., Any]]] = {}
PLUGIN_CATALOG: Dict[str, Dict[str, Any]] = {}

# re-export for tests
compute_checksum = _compute_checksum


from .api import Codec, FEC, Simulator


def register_codec(name: str, codec: Codec | type[Codec]) -> None:
    """Register a codec implementation under ``name``."""

    if isinstance(codec, type):
        if not issubclass(codec, Codec):
            raise TypeError("codec must subclass Codec")
        inst = codec()
    else:
        if not isinstance(codec, Codec):
            raise TypeError("codec must subclass Codec")
        inst = codec

    CODEC_REGISTRY[name] = {"encode": inst.encode, "decode": inst.decode}


def register_fec(name: str, fec: FEC | type[FEC]) -> None:
    """Register a FEC backend under ``name``."""

    if isinstance(fec, type):
        if not issubclass(fec, FEC):
            raise TypeError("FEC must subclass FEC")
        inst = fec()
    else:
        if not isinstance(fec, FEC):
            raise TypeError("FEC must subclass FEC")
        inst = fec

    FEC_REGISTRY[name] = {"encode": inst.encode, "decode": inst.decode}


def register_simulator(name: str, channel: Simulator) -> None:
    """Register a read simulator under ``name``."""

    if not isinstance(channel, Simulator):
        raise TypeError("simulator must subclass Simulator")

    _register_simulator(name, channel)








def install_registry_plugins(url: str | None = None) -> None:
    """Install plugin packages listed in a YAML registry at ``url``."""

    if url is None:
        return

    yaml_module = yaml
    if yaml_module is None:
        try:  # lazy import for environments where PyYAML may be installed later
            import yaml as yaml_module
        except Exception:  # pragma: no cover - optional
            logger.warning("YAML support unavailable; skipping registry %s", url)
            return
        else:
            globals()["yaml"] = yaml_module
    if yaml_module is None:  # for type checkers
        logger.warning("YAML support unavailable; skipping registry %s", url)
        return

    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            raw = response.read()
        data = yaml_module.safe_load(raw) or {}
    except Exception as exc:
        logger.warning("Failed to fetch or parse plugin registry %s: %s", url, exc)
        raise ValueError("Invalid plugin registry YAML") from exc

    for entry in data.get("packages", []):
        spec = ""
        if isinstance(entry, dict):
            spec = str(entry.get("spec") or entry.get("package") or entry.get("url") or "")
        else:
            spec = str(entry)

        if not spec:
            logger.warning("Missing spec for plugin entry %s", entry)
            continue

        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", spec])
        except Exception as exc:  # pragma: no cover - install error path
            logger.warning("Failed to install plugin %s from registry: %s", spec, exc)


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
                else (
                    item.load()
                    if hasattr(item, "load")
                    else importlib.import_module(name)
                )
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


def load_builtin_plugins() -> None:
    """Load built-in plugins and clear existing registries."""

    CODEC_REGISTRY.clear()
    FEC_REGISTRY.clear()
    SIMULATOR_REGISTRY.clear()

    builtin = importlib.import_module("genecoder.builtin_plugins")
    if hasattr(builtin, "register_builtin_plugins"):
        builtin.register_builtin_plugins()




def load_entry_point_plugins() -> list[str]:
    """Load plugins registered via Python entry points."""

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

    return failures


def load_local_plugins() -> list[str]:
    """Load plugins from a local ``plugins`` package if present."""

    failures: list[str] = []
    try:
        import plugins
    except ModuleNotFoundError:
        return failures

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

    return failures


_initialized = False


def load_plugins() -> None:
    """Load built-in, entry point and local plugins and fetch catalog entries."""

    load_builtin_plugins()
    failures = load_entry_point_plugins()
    failures.extend(load_local_plugins())
    if failures:
        logger.warning("Failed to import plugins: %s", ", ".join(failures))


def init_plugins() -> None:
    """Initialize plugins once with error handling."""

    global _initialized
    if _initialized:
        return
    try:
        load_plugins()
    except Exception as exc:  # pragma: no cover - unexpected error path
        logger.warning("Failed to load plugins: %s", exc)
    _initialized = True


def _verify_catalog_signature(data: bytes, signature_b64: str) -> bool:
    """Return ``True`` if ``signature_b64`` verifies ``data`` using the public key.

    The key path is read from the ``GENECODER_CATALOG_PUBLIC_KEY`` environment
    variable. ``False`` is returned on any failure.
    """

    key_path = os.getenv("GENECODER_CATALOG_PUBLIC_KEY")
    if not key_path:
        return False

    try:
        public_key = Path(key_path).read_bytes()
    except Exception:
        return False

    try:
        signature = base64.b64decode(signature_b64, validate=True)
    except Exception:
        return False

    try:
        compute_checksum(data, signature=signature, public_key=public_key)
    except Exception:
        return False
    return True

