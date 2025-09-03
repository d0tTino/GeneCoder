import urllib.error
import urllib.request

import pytest

import genecoder.plugin_manager as plugins


def test_registry_remote_rejected_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remote registries are blocked when offline is true."""

    def fake_urlopen(url: str, *, timeout: int | None = None):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="GENECODER_ALLOW_NETWORK"):
        plugins.install_registry_plugins(
            "https://example.com/plugins.yaml", offline=True, allow_network=True
        )
