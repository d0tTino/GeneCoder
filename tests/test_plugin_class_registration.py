from importlib.metadata import EntryPoint
from pathlib import Path

import pytest
import genecoder.plugin_manager as plugins


def test_class_based_plugins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    codec_mod = tmp_path / "cmod.py"
    codec_mod.write_text(
        """
from typing import Any
from genecoder.codecs import BaseCodec

class DummyCodec(BaseCodec):
    def encode(self, data: bytes, /, **kwargs: Any) -> str:
        return data.decode()[::-1]

    def decode(self, encoded: str, /, **kwargs: Any) -> bytes:
        return encoded[::-1].encode()

def register(register_codec):
    register_codec('dummy_cls', DummyCodec)
"""
    )

    fec_mod = tmp_path / "fmod.py"
    fec_mod.write_text(
        """
from typing import Mapping, Any
from genecoder.codecs import BaseFEC

class DummyFEC(BaseFEC):
    def encode(self, data: bytes, /, **kwargs: Any) -> tuple[bytes, Mapping[str, Any]]:
        return data + b'x', {}

    def decode(self, encoded: bytes, info: Mapping[str, Any], /, **kwargs: Any) -> tuple[bytes, int]:
        return encoded[:-1], 0

def register(register_fec):
    register_fec('dummy_fec_cls', DummyFEC)
"""
    )

    monkeypatch.syspath_prepend(str(tmp_path))

    ep_codec = EntryPoint(name="dummy_cls", value="cmod", group="genecoder.plugins")
    ep_fec = EntryPoint(name="dummy_fec_cls", value="fmod", group="genecoder.fec")

    monkeypatch.setattr(
        plugins,
        "entry_points",
        lambda *, group=None: [e for e in (ep_codec, ep_fec) if e.group == group],
    )

    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()

    plugins.load_plugins()

    assert "dummy_cls" in plugins.CODEC_REGISTRY
    assert plugins.CODEC_REGISTRY["dummy_cls"]["encode"](b"abc") == "cba"

    assert "dummy_fec_cls" in plugins.FEC_REGISTRY
    decoded, corr = plugins.FEC_REGISTRY["dummy_fec_cls"]["decode"](b"abcx", {})
    assert decoded == b"abc" and corr == 0
