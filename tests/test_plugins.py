from pathlib import Path

import pytest

from genecoder import plugins


def test_external_plugin_package(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pkg = tmp_path / "plugins"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "ext.py").write_text(
        """
from typing import Callable, Mapping, Tuple
from genecoder.api import Codec, FEC

class ExtCodec(Codec):
    def encode(self, data: bytes) -> str:
        return 'Y'

    def decode(self, text: str) -> bytes:
        return b'Y'

class ExtFEC(FEC):
    def encode(self, data: bytes) -> Tuple[bytes, Mapping[str, int]]:
        return data + b'ZZ', {'n': 2}

    def decode(self, encoded: bytes, info: Mapping[str, int]) -> Tuple[bytes, int]:
        return encoded[:-info['n']], info['n']

def register(register_codec: Callable[[str, type[Codec]], None]):
    register_codec('ext_codec', ExtCodec)

def register_fec(register_fec: Callable[[str, type[FEC]], None]):
    register_fec('ext_fec', ExtFEC)
"""
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    import plugins as builtin_plugins
    monkeypatch.setattr(builtin_plugins, '__path__', list(getattr(builtin_plugins, '__path__', [])) + [str(pkg)])
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()
    plugins.load_plugins()
    assert 'ext_codec' in plugins.CODEC_REGISTRY
    assert 'ext_fec' in plugins.FEC_REGISTRY
    # restore built-ins
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()
    plugins.load_plugins()
