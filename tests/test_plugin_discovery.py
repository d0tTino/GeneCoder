import genecoder.plugin_manager as plugins
import plugins as builtin_plugins


def test_load_plugins_from_local_package(tmp_path, monkeypatch):
    pkg = tmp_path / "plugins"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "tmp_codec.py").write_text(
        """
from typing import Callable, Any
from genecoder.api import Codec

class TmpCodec(Codec):
    def encode(self, data: bytes, /, **kwargs: Any) -> str:
        return 'X'

    def decode(self, text: str, /, **kwargs: Any) -> bytes:
        return b'X'

def register(register_codec: Callable[[str, type[Codec]], None]):
    register_codec('tmp', TmpCodec)
"""
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(builtin_plugins, '__path__', list(builtin_plugins.__path__) + [str(pkg)])
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()
    plugins.load_plugins()
    assert 'tmp' in plugins.CODEC_REGISTRY
    # restore built-ins
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()
    plugins.load_plugins()



