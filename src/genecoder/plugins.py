from __future__ import annotations

from typing import Callable, Dict, Any

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


def load_plugins() -> None:
    """Load plugins defined via GeneCoder entry points."""
    for ep in entry_points(group="genecoder.plugins"):
        try:
            plugin = ep.load()
        except Exception as exc:  # pragma: no cover - error path
            logger.warning("Failed to import plugin %s: %s", ep.value, exc)
            continue
        register = getattr(plugin, "register", None)
        if callable(register):
            register(register_codec)

    for ep in entry_points(group="genecoder.fec"):
        try:
            plugin = ep.load()
        except Exception as exc:  # pragma: no cover - error path
            logger.warning("Failed to import FEC plugin %s: %s", ep.value, exc)
            continue
        register = getattr(plugin, "register", None)
        if callable(register):
            register(register_fec)

    for ep in entry_points(group="genecoder.simulators"):
        try:
            plugin = ep.load()
        except Exception as exc:  # pragma: no cover - error path
            logger.warning("Failed to import simulator plugin %s: %s", ep.value, exc)
            continue
        register = getattr(plugin, "register", None)
        if callable(register):
            register(register_simulator)

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

    # Load built-in back-ends directly when running from source
    from plugins import reverse_codec as _reverse
    _reverse.register(register_codec)
    from . import reed_solomon_codec as _rs
    _rs.register(register_fec)
    from . import ldpc_codec as _ldpc
    _ldpc.register(register_fec)
    from . import fountain_codec as _fountain
    _fountain.register(register_fec)
    from . import bch_codec as _bch
    _bch.register(register_fec)
    from . import raptorq_codec as _raptorq
    _raptorq.register(register_fec)
    from .fec import framed as _framed
    _framed.register(register_fec)
    from . import nanopore_sim as _nano
    if hasattr(_nano, "register"):
        _nano.register(register_simulator)
    else:
        for name in _nano.SIMULATOR_ADAPTERS:
            register_simulator(name, _nano.Channel(name))

    from . import channel_sim as _chan
    if hasattr(_chan, "register"):
        _chan.register(register_simulator)
    else:
        register_simulator("simple", _chan.Channel())

    from . import error_simulation as _err
    if hasattr(_err, "register"):
        _err.register(register_simulator)
    else:
        register_simulator("indel", _err.Channel())
