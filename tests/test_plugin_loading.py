import tomllib
from pathlib import Path

import pytest
from genecoder import (
    CODEC_REGISTRY,
    FEC_REGISTRY,
    SIMULATOR_REGISTRY,
    load_plugins,
)

load_plugins()


def test_reverse_codec_plugin_loaded() -> None:
    assert "reverse" in CODEC_REGISTRY
    codec = CODEC_REGISTRY["reverse"]
    encoded = codec["encode"](b"abc")
    assert encoded == "cba"
    assert codec["decode"](encoded) == b"abc"


def test_fec_plugins_registered() -> None:
    assert "reed_solomon" in FEC_REGISTRY
    assert "ldpc" in FEC_REGISTRY
    assert "fountain" in FEC_REGISTRY
    assert "bch" in FEC_REGISTRY
    assert "raptorq" in FEC_REGISTRY


def test_simulator_plugins_registered() -> None:
    from genecoder.channels.base import BaseChannel

    assert isinstance(SIMULATOR_REGISTRY, dict)
    assert all(isinstance(ch, BaseChannel) for ch in SIMULATOR_REGISTRY.values())


def test_example_plugins_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    from importlib.metadata import EntryPoint
    from pathlib import Path

    import genecoder.plugin_manager as plugins

    root = Path(__file__).resolve().parents[1] / "plugins-examples"
    monkeypatch.syspath_prepend(str(root / "example_codec"))
    monkeypatch.syspath_prepend(str(root / "example_fec"))
    monkeypatch.syspath_prepend(str(root / "example_simulator"))
    monkeypatch.syspath_prepend(str(root / "example_visualizer"))

    def fake_entry_points(*, group: str | None = None) -> list[EntryPoint]:
        if group == "genecoder.plugins":
            return [EntryPoint(name="example", value="example_codec", group=group)]
        if group == "genecoder.fec":
            return [EntryPoint(name="example", value="example_fec", group=group)]
        if group == "genecoder.simulators":
            return [EntryPoint(name="example", value="example_simulator", group=group)]
        if group == "genecoder.visualizers":
            return [EntryPoint(name="example", value="example_visualizer", group=group)]
        return []

    monkeypatch.setattr(plugins, "entry_points", fake_entry_points)

    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()
    plugins.VISUALIZER_REGISTRY.clear()

    plugins.load_plugins()

    assert "reverse" in plugins.CODEC_REGISTRY
    assert "example" in plugins.CODEC_REGISTRY
    assert "example" in plugins.FEC_REGISTRY
    assert "example" in plugins.SIMULATOR_REGISTRY
    assert "example" in plugins.VISUALIZER_REGISTRY


def test_load_plugins_idempotent() -> None:
    CODEC_REGISTRY.clear()
    FEC_REGISTRY.clear()
    SIMULATOR_REGISTRY.clear()

    load_plugins()

    codec_keys = set(CODEC_REGISTRY)
    fec_keys = set(FEC_REGISTRY)
    sim_keys = set(SIMULATOR_REGISTRY)

    load_plugins()

    assert set(CODEC_REGISTRY) == codec_keys
    assert set(FEC_REGISTRY) == fec_keys
    assert set(SIMULATOR_REGISTRY) == sim_keys




def test_simulator_entry_points_avoid_deprecated_shims() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    simulators = data["tool"]["poetry"]["plugins"]["genecoder.simulators"]

    deprecated_modules = {
        "genecoder.error_simulation",
        "genecoder.channel_sim",
        "genecoder.compat.error_simulation",
        "genecoder.compat.channel_sim",
    }
    for module_path in simulators.values():
        assert module_path not in deprecated_modules

    assert simulators["simple"] == "genecoder.simulators.simple"
    assert simulators["indel"] == "genecoder.simulators.indel"
