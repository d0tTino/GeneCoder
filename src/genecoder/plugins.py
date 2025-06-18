from __future__ import annotations

from typing import Callable, Dict, Any
from importlib.metadata import entry_points
import importlib
import pkgutil

CODEC_REGISTRY: Dict[str, Dict[str, Callable[..., Any]]] = {}


def register_codec(name: str, encode: Callable[..., Any], decode: Callable[..., Any]) -> None:
    """Register a codec implementation under ``name``."""
    CODEC_REGISTRY[name] = {"encode": encode, "decode": decode}


def load_plugins() -> None:
    """Load plugins defined via ``genecoder.plugins`` entry points."""
    for ep in entry_points(group="genecoder.plugins"):
        plugin = ep.load()
        register = getattr(plugin, "register", None)
        if callable(register):
            register(register_codec)

    # Also load plugins from a local ``plugins`` package if present
    try:
        import plugins
    except ModuleNotFoundError:
        return
    for _, module_name, _ in pkgutil.iter_modules(plugins.__path__):
        module = importlib.import_module(f"plugins.{module_name}")
        register = getattr(module, "register", None)
        if callable(register):
            register(register_codec)
