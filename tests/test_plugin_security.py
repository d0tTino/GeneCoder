import base64
from pathlib import Path
import logging

import pytest

pytest.importorskip("portalocker")
pytest.importorskip("yaml")

import genecoder.plugin_manager as plugins
from genecoder.plugin_security import compute_checksum


class DummyResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._data


def test_registry_invalid_signature(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    pkg = b"PKG"
    checksum = compute_checksum(pkg)
    sig_b64 = base64.b64encode(b"sig").decode()

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkg.whl\n    checksum: {checksum}\n    signature: {sig_b64}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    installs: list[list[str]] = []
    key = Path("/tmp/pub.pem")
    key.write_text("PUB")

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)

    def fake_compute(
        data: bytes,
        *,
        signature: bytes | None = None,
        public_key: bytes | None = None,
    ) -> str:
        if signature is not None:
            raise ValueError("bad sig")
        return compute_checksum(data)

    monkeypatch.setattr(plugins, "compute_checksum", fake_compute)

    with pytest.raises(ValueError, match="Invalid signature"):
        with caplog.at_level(logging.ERROR):
            plugins.install_registry_plugins()

    assert not installs
    assert "Invalid signature for plugin https://example.com/pkg.whl" in caplog.text
