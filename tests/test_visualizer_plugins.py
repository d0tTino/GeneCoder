from importlib.metadata import EntryPoint
from pathlib import Path

import pytest

import genecoder.plugin_manager as plugins
from genecoder.app_helpers import EncodeResult


def test_visualizer_entry_point(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mod = tmp_path / "vmod.py"
    mod.write_text(
        """
class DummyBase:
    def visualize(self, result, **kw):
        pass

def register(register_visualizer):
    from genecoder.sdk.plugins import Visualizer
    from genecoder.app_helpers import EncodeResult, DecodeResult

    class DummyViz(DummyBase, Visualizer):
        def visualize(self, result: EncodeResult | DecodeResult, **kw) -> None:
            super().visualize(result, **kw)

    register_visualizer('dummy_vis', DummyViz)
"""
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    src_path = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(src_path))
    ep = EntryPoint(name="dummy_vis", value="vmod", group="genecoder.visualizers")
    monkeypatch.setattr(
        plugins,
        "entry_points",
        lambda *, group=None: [ep] if group == "genecoder.visualizers" else [],
    )
    monkeypatch.setattr(plugins, "load_builtin_plugins", lambda: None)
    monkeypatch.setattr(plugins, "load_local_plugins", lambda: [])

    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.VISUALIZER_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()

    failures = plugins.load_entry_point_plugins()

    assert failures == []
    assert "dummy_vis" in plugins.VISUALIZER_REGISTRY
    plugins.VISUALIZER_REGISTRY["dummy_vis"](
        EncodeResult(fasta="", encoded_dna="AC", metrics={}, info_messages=[])
    )
