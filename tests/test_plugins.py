from pathlib import Path

import pytest

from genecoder import plugins


def test_external_plugin_package(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pkg = tmp_path / "plugins"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "ext.py").write_text(
        """
from typing import Callable, Tuple

def register(register_codec: Callable[[str, Callable[[bytes], str], Callable[[str], bytes]], None]):
    def enc(data: bytes) -> str:
        return 'Y'
    def dec(text: str) -> bytes:
        return b'Y'
    register_codec('ext_codec', enc, dec)

def register_fec(register_fec: Callable[[str, Callable[[bytes], Tuple[bytes, int]], Callable[[bytes, int], Tuple[bytes, int]]], None]):
    def enc(data: bytes) -> Tuple[bytes, int]:
        return data + b'ZZ', 2
    def dec(data: bytes, nsym: int) -> Tuple[bytes, int]:
        return data[:-nsym], nsym
    register_fec('ext_fec', enc, dec)
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
