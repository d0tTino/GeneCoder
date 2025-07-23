import pytest
import genecoder.plugin_manager as plugins

class DummyResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False
    def read(self) -> bytes:
        return self._data

def test_install_registry_plugins_malformed_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        assert url == "https://example.com/plugins.yaml"
        return DummyResponse(b"not: [yaml")

    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(ValueError, match="Invalid plugin registry YAML"):
        plugins.install_registry_plugins("https://example.com/plugins.yaml")
