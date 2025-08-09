import pytest

import genecoder.plugin_manager as plugins


def test_remote_registry_rejected_in_offline_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remote registries are blocked when offline is true."""
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    with pytest.raises(RuntimeError, match="Offline mode forbids fetching registry"):
        plugins.install_registry_plugins("https://example.com/plugins.yaml", offline=True)

