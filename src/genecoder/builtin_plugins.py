from __future__ import annotations

"""Register built-in GeneCoder plugins."""

from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

from .plugin_runtime.descriptors import (
    PLUGIN_DESCRIPTOR_VERSION,
    RegistrationCapabilities,
    RuntimePluginDescriptor,
    ValidationContract,
)
from .plugin_runtime.registry import register_plugin


def _register_from_module(module: ModuleType, descriptor_kind: str, name_hint: str) -> None:
    plugin_name = getattr(module, "PLUGIN_NAME", name_hint)
    impl = getattr(module, "PLUGIN", None)
    if impl is None:
        register = getattr(module, "register", None)
        if callable(register):
            # Compatibility: allow old register(function) modules while built-ins migrate.
            kind_map = {
                "codec": lambda n, v: register_plugin(RuntimePluginDescriptor(api_version=PLUGIN_DESCRIPTOR_VERSION, name=n, kind="codec", implementation=v, capabilities=RegistrationCapabilities(deterministic=True), validation=ValidationContract(encode_input="bytes", encode_output="sequence", decode_input="sequence|batch", decode_output="bytes"))),
                "fec": lambda n, v: register_plugin(RuntimePluginDescriptor(api_version=PLUGIN_DESCRIPTOR_VERSION, name=n, kind="fec", implementation=v)),
                "simulator": lambda n, v: register_plugin(RuntimePluginDescriptor(api_version=PLUGIN_DESCRIPTOR_VERSION, name=n, kind="simulator", implementation=v)),
                "visualizer": lambda n, v: register_plugin(RuntimePluginDescriptor(api_version=PLUGIN_DESCRIPTOR_VERSION, name=n, kind="visualizer", implementation=v)),
            }
            register(kind_map[descriptor_kind])
            return
        raise ValueError(f"Builtin module {module.__name__} does not expose a plugin implementation")

    register_plugin(
        RuntimePluginDescriptor(
            api_version=PLUGIN_DESCRIPTOR_VERSION,
            name=plugin_name,
            kind=descriptor_kind,
            implementation=impl,
            capabilities=RegistrationCapabilities(deterministic=True),
            validation=ValidationContract(
                encode_input="bytes",
                encode_output="sequence" if descriptor_kind == "codec" else "bytes",
                decode_input="sequence|batch" if descriptor_kind == "codec" else "bytes",
                decode_output="bytes",
            ),
            metadata={"builtin": True},
        )
    )


def _load_and_register(items: list[str], kind: str) -> None:
    for name in items:
        try:
            module = import_module(name)
        except Exception:
            continue
        _register_from_module(module, kind, name.rsplit(".", 1)[-1])


def register_builtin_plugins() -> None:
    """Register all built-in GeneCoder plugins."""

    try:
        module = import_module("plugins.reverse_codec")
    except ModuleNotFoundError:  # pragma: no cover
        spec = spec_from_file_location(
            "plugins.reverse_codec",
            Path(__file__).resolve().parents[1] / "plugins" / "reverse_codec.py",
        )
        assert spec and spec.loader
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
    _register_from_module(module, "codec", "reverse")

    _load_and_register([
        "genecoder.chamaeleo_codec",
        "genecoder.dnachisel_fixer",
    ], "codec")

    _load_and_register([
        "genecoder.reed_solomon_codec",
        "genecoder.ldpc_codec",
        "genecoder.fountain_codec",
        "genecoder.bch_codec",
        "genecoder.raptorq_codec",
    ], "fec")

    _load_and_register([
        "genecoder.error_simulation",
        "genecoder.simulators.decay",
        "genecoder.simulators.illumina",
        "genecoder.insilicoseq_adapter",
        "genecoder.simulators.nanopore",
        "genecoder.d2sim_adapter",
        "genecoder.dnarsim_adapter",
        "genecoder.squigulator_adapter",
        "genecoder.desp_adapter",
    ], "simulator")

    _load_and_register([
        "genecoder.default_visualizer",
    ], "visualizer")
