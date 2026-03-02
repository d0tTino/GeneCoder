import types
import urllib.error
import urllib.request

import pytest

import genecoder.plugin_manager as plugins
from genecoder.sdk.plugins import Codec


def test_registry_remote_rejected_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remote registries are blocked when offline is true."""

    def fake_urlopen(url: str, *, timeout: int | None = None):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="GENECODER_ALLOW_NETWORK"):
        plugins.install_registry_plugins(
            "https://example.com/plugins.yaml", offline=True, allow_network=True
        )


def test_entry_point_lazy_loading_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    module = types.ModuleType("lazy_ep_mod")

    class LazyCodec(Codec):  # type: ignore[misc]
        def encode(self, data: bytes, /, **kwargs: object) -> str:
            return data.decode("ascii")

        def decode(self, text: str, /, **kwargs: object) -> bytes:
            return text.encode("ascii")

    def register(register_codec):
        register_codec("lazy", LazyCodec)

    module.register = register  # type: ignore[attr-defined]
    module.PLUGIN_METADATA = {
        "name": "lazy",
        "version": "1.0",
        "interfaces": ["codec"],
        "license": "MIT",
    }

    class EP:
        name = "lazy"
        group = "genecoder.plugins"
        value = "lazy_ep_mod"

        def load(self):
            calls.append("loaded")
            return module

    def fake_entry_points(*, group: str | None = None):
        if group in (None, "genecoder.plugins"):
            return [EP()]
        return []

    monkeypatch.setattr(plugins, "entry_points", fake_entry_points)
    monkeypatch.setenv("GENECODER_OFFLINE", "1")
    monkeypatch.delenv("GENECODER_ALLOW_NETWORK", raising=False)

    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()
    plugins.VISUALIZER_REGISTRY.clear()

    plugins.load_plugins()

    assert "lazy" in plugins.CODEC_REGISTRY
    assert calls == []

    codec_entry = plugins.CODEC_REGISTRY["lazy"]
    assert calls == []
    assert codec_entry["encode"](b"hi") == "hi"
    assert calls == ["loaded"]
    assert codec_entry["decode"]("hi") == b"hi"
