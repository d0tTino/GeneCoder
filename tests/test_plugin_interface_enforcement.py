from importlib.metadata import EntryPoint
from pathlib import Path

import pytest
import genecoder.plugin_manager as plugins


def test_plugin_signature_validation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    codec_mod = tmp_path / "bad_codec.py"
    codec_mod.write_text(
        """
from genecoder.codecs import BaseCodec

class BadCodec(BaseCodec):
    def encode(self, data: bytes, extra: int, /, **kwargs) -> bytes:
        return b""

    def decode(self, encoded: bytes, /, **kwargs) -> bytes:
        return b""

def register(register_codec):
    register_codec("bad", BadCodec)
"""
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    ep = EntryPoint(name="bad", value="bad_codec", group="genecoder.plugins")
    monkeypatch.setattr(
        plugins, "entry_points", lambda *, group=None: [ep] if group == "genecoder.plugins" else []
    )
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()
    plugins.VISUALIZER_REGISTRY.clear()
    with pytest.raises(TypeError, match="codec encode has incompatible signature"):
        plugins.load_plugins()


def test_fec_missing_method(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fec_mod = tmp_path / "bad_fec.py"
    fec_mod.write_text(
        """
from genecoder.sdk.plugins import FEC

class BadFEC(FEC):
    def encode(self, data: bytes, /, **kwargs) -> tuple[bytes, dict[str, object]]:
        return b"", {}
    decode = None  # type: ignore[assignment]

def register(register_fec):
    register_fec("badfec", BadFEC)
"""
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    ep = EntryPoint(name="badfec", value="bad_fec", group="genecoder.fec")
    monkeypatch.setattr(
        plugins, "entry_points", lambda *, group=None: [ep] if group == "genecoder.fec" else []
    )
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()
    plugins.VISUALIZER_REGISTRY.clear()
    with pytest.raises(TypeError, match="FEC missing required method decode"):
        plugins.load_plugins()


def test_simulator_missing_method(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sim_mod = tmp_path / "bad_sim.py"
    sim_mod.write_text(
        """
from genecoder.sdk.plugins import Simulator

class BadSim(Simulator):
    simulate = None  # type: ignore[assignment]

def register(register_simulator):
    register_simulator("badsim", BadSim)
"""
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    ep = EntryPoint(name="badsim", value="bad_sim", group="genecoder.simulators")
    monkeypatch.setattr(
        plugins, "entry_points", lambda *, group=None: [ep] if group == "genecoder.simulators" else []
    )
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()
    plugins.VISUALIZER_REGISTRY.clear()
    with pytest.raises(TypeError, match="simulator missing required method simulate"):
        plugins.load_plugins()


def test_visualizer_missing_method(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    vis_mod = tmp_path / "bad_vis.py"
    vis_mod.write_text(
        """
from genecoder.sdk.plugins import Visualizer

class BadVis(Visualizer):
    visualize = None  # type: ignore[assignment]

def register(register_visualizer):
    register_visualizer("badvis", BadVis)
"""
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    ep = EntryPoint(name="badvis", value="bad_vis", group="genecoder.visualizers")
    monkeypatch.setattr(
        plugins, "entry_points", lambda *, group=None: [ep] if group == "genecoder.visualizers" else []
    )
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()
    plugins.VISUALIZER_REGISTRY.clear()
    with pytest.raises(TypeError, match="visualizer missing required method visualize"):
        plugins.load_plugins()
