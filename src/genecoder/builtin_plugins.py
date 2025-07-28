from __future__ import annotations

"""Register built-in GeneCoder plugins."""

from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from .plugin_manager import (
    register_codec,
    register_fec,
    register_simulator,
    register_visualizer,
    _load_and_register,
)


def register_builtin_plugins() -> None:
    """Register all built-in GeneCoder plugins."""

    try:
        module = import_module("plugins.reverse_codec")
    except ModuleNotFoundError:  # pragma: no cover - fallback when a plugins.py module is present
        spec = spec_from_file_location(
            "plugins.reverse_codec",
            Path(__file__).resolve().parents[1] / "plugins" / "reverse_codec.py",
        )
        assert spec and spec.loader
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
    register = getattr(module, "register", None)
    if callable(register):
        register(register_codec)

    _load_and_register(
        [
            "genecoder.chamaeleo_codec",
        ],
        register_codec,
        "builtin",
    )

    _load_and_register(
        [
            "genecoder.reed_solomon_codec",
            "genecoder.ldpc_codec",
            "genecoder.fountain_codec",
            "genecoder.bch_codec",
            "genecoder.raptorq_codec",
            "genecoder.fec.framed",
        ],
        register_fec,
        "builtin",
    )

    _load_and_register(
        [
            "genecoder.nanopore_sim",
            "genecoder.channel_sim",
            "genecoder.error_simulation",
            "genecoder.simulators.illumina",
            "genecoder.simulators.nanopore",
            "genecoder.insilicoseq_adapter",
            "genecoder.desp_adapter",
        ],
        register_simulator,
        "builtin",
    )

    _load_and_register(
        ["genecoder.default_visualizer"],
        register_visualizer,
        "builtin",
    )
