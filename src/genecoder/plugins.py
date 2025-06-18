from __future__ import annotations

from typing import Callable, Dict, Any
from importlib.metadata import entry_points
import importlib
import pkgutil

CODEC_REGISTRY: Dict[str, Dict[str, Callable[..., Any]]] = {}
FEC_REGISTRY: Dict[str, Dict[str, Callable[..., Any]]] = {}
SIMULATOR_REGISTRY: Dict[str, Callable[..., Any]] = {}


def register_codec(name: str, encode: Callable[..., Any], decode: Callable[..., Any]) -> None:
    """Register a codec implementation under ``name``."""
    CODEC_REGISTRY[name] = {"encode": encode, "decode": decode}


def register_fec(name: str, encode: Callable[..., Any], decode: Callable[..., Any]) -> None:
    """Register a FEC backend under ``name``."""
    FEC_REGISTRY[name] = {"encode": encode, "decode": decode}


def register_simulator(name: str, simulate: Callable[..., Any]) -> None:
    """Register a read simulator under ``name``."""
    SIMULATOR_REGISTRY[name] = simulate


def load_plugins() -> None:
    """Load plugins defined via GeneCoder entry points."""
    for ep in entry_points(group="genecoder.plugins"):
        plugin = ep.load()
        register = getattr(plugin, "register", None)
        if callable(register):
            register(register_codec)

    for ep in entry_points(group="genecoder.fec"):
        plugin = ep.load()
        register = getattr(plugin, "register", None)
        if callable(register):
            register(register_fec)

    for ep in entry_points(group="genecoder.simulators"):
        plugin = ep.load()
        register = getattr(plugin, "register", None)
        if callable(register):
            register(register_simulator)

    # Also load plugins from a local ``plugins`` package if present
    try:
        import plugins
    except ModuleNotFoundError:
        plugins = None
    if plugins is not None:
        for _, module_name, _ in pkgutil.iter_modules(plugins.__path__):
            module = importlib.import_module(f"plugins.{module_name}")
            register = getattr(module, "register", None)
            if callable(register):
                register(register_codec)
            register_f = getattr(module, "register_fec", None)
            if callable(register_f):
                register_f(register_fec)
            register_s = getattr(module, "register_simulator", None)
            if callable(register_s):
                register_s(register_simulator)

    # Load built-in back-ends directly when running from source
    from . import reed_solomon_codec as _rs
    _rs.register(register_fec)
    from . import ldpc_codec as _ldpc
    _ldpc.register(register_fec)
    from . import fountain_codec as _fountain
    _fountain.register(register_fec)
    from . import nanopore_sim as _nano
    if hasattr(_nano, "register"):
        _nano.register(register_simulator)
    else:
        for name in _nano.SIMULATOR_ADAPTERS:
            def wrapper(seq: str, error_rate: float = 0.05, *, _name: str = name) -> str:
                return _nano.simulate_reads(seq, _name, error_rate)

            register_simulator(name, wrapper)

        register_simulator("none", lambda seq, error_rate=0.05: seq)
