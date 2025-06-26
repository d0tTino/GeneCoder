from __future__ import annotations

from typing import Callable, Dict, Any, Iterable
from types import ModuleType

from .channels.base import BaseChannel
from importlib.metadata import entry_points
import importlib
import logging
import pkgutil

logger = logging.getLogger(__name__)

CODEC_REGISTRY: Dict[str, Dict[str, Callable[..., Any]]] = {}
FEC_REGISTRY: Dict[str, Dict[str, Callable[..., Any]]] = {}
SIMULATOR_REGISTRY: Dict[str, BaseChannel] = {}


def register_codec(name: str, encode: Callable[..., Any], decode: Callable[..., Any]) -> None:
    """Register a codec implementation under ``name``."""
    CODEC_REGISTRY[name] = {"encode": encode, "decode": decode}


def register_fec(name: str, encode: Callable[..., Any], decode: Callable[..., Any]) -> None:
    """Register a FEC backend under ``name``."""
    FEC_REGISTRY[name] = {"encode": encode, "decode": decode}


def register_simulator(name: str, channel: BaseChannel) -> None:
    """Register a read simulator under ``name``."""
    SIMULATOR_REGISTRY[name] = channel


def _load_and_register(items: Iterable[Any], registrar: Callable[..., Any], kind: str) -> None:
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
        except Exception as exc:  # pragma: no cover - error path
            logger.warning("Failed to import %s plugin %s: %s", kind, name, exc)
            continue
        register = getattr(module, "register", None)
        if callable(register):
            register(registrar)


def load_plugins() -> None:
    """Load plugins defined via GeneCoder entry points."""

    # First load built-in plugin modules
    builtin = importlib.import_module("genecoder.builtin_plugins")
    if hasattr(builtin, "register_builtin_plugins"):
        builtin.register_builtin_plugins()

    _load_and_register(entry_points(group="genecoder.plugins"), register_codec, "codec")
    _load_and_register(entry_points(group="genecoder.fec"), register_fec, "FEC")
    _load_and_register(
        entry_points(group="genecoder.simulators"), register_simulator, "simulator"
    )

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
                except Exception as exc:  # pragma: no cover - error path
                    logger.warning(
                        "Failed to import local plugin %s: %s", module_name, exc
                    )
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

