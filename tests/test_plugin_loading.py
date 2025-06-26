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
    assert "framed" in FEC_REGISTRY


def test_simulator_plugins_registered() -> None:
    from genecoder.channels.base import BaseChannel

    assert isinstance(SIMULATOR_REGISTRY, dict)
    assert all(isinstance(ch, BaseChannel) for ch in SIMULATOR_REGISTRY.values())


def test_example_plugins_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    from importlib.metadata import EntryPoint
    from pathlib import Path

    import genecoder.plugins as plugins

    root = Path(__file__).resolve().parents[1] / "plugins-examples"
    monkeypatch.syspath_prepend(str(root / "example_codec"))
    monkeypatch.syspath_prepend(str(root / "example_fec"))
    monkeypatch.syspath_prepend(str(root / "example_simulator"))

    def fake_entry_points(*, group: str | None = None):
        if group == "genecoder.plugins":
            return [EntryPoint(name="example", value="example_codec", group=group)]
        if group == "genecoder.fec":
            return [EntryPoint(name="example", value="example_fec", group=group)]
        if group == "genecoder.simulators":
            return [EntryPoint(name="example", value="example_simulator", group=group)]
        return []

    monkeypatch.setattr(plugins, "entry_points", fake_entry_points)

    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()

    plugins.load_plugins()

    assert "reverse" in plugins.CODEC_REGISTRY
    assert "example" in plugins.CODEC_REGISTRY
    assert "example" in plugins.FEC_REGISTRY
    assert "example" in plugins.SIMULATOR_REGISTRY

