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
    with pytest.raises(TypeError):
        plugins.load_plugins()
