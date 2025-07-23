import base64
from pathlib import Path

import pytest

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


def test_load_plugins_with_signed_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = b"PKG"
    checksum = compute_checksum(pkg)
    sig = base64.b64encode(b"sig").decode()

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkg.whl\n    checksum: {checksum}\n    signature: {sig}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    key = Path("/tmp/pub.pem")
    key.write_text("PUB")
    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(
        plugins,
        "compute_checksum",
        lambda d, *, signature=None, public_key=None: compute_checksum(d),
    )
    monkeypatch.setattr(plugins, "verify_signature", lambda d, s, k: None)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])

    plugins.install_registry_plugins()
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()

    plugins.load_plugins()

    assert "reverse" in plugins.CODEC_REGISTRY


def test_load_plugins_registry_missing_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg = b"PKG"
    checksum = compute_checksum(pkg)

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkg.whl\n    checksum: {checksum}\n"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    key = Path("/tmp/pub.pem")
    key.write_text("PUB")
    monkeypatch.setenv(
        "GENECODER_PLUGIN_REGISTRY_URL",
        "https://example.com/plugins.yaml",
    )
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(
        plugins,
        "compute_checksum",
        lambda d, *, signature=None, public_key=None: compute_checksum(d),
    )
    monkeypatch.setattr(plugins, "verify_signature", lambda d, s, k: None)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])

    with pytest.raises(ValueError, match="Missing signature"):
        plugins.install_registry_plugins()


def test_load_plugins_registry_checksum_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg = b"PKG"
    wrong_checksum = compute_checksum(b"WRONG")
    sig = base64.b64encode(b"sig").decode()

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkg.whl\n    checksum: {wrong_checksum}\n    signature: {sig}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    key = Path("/tmp/pub.pem")
    key.write_text("PUB")
    monkeypatch.setenv(
        "GENECODER_PLUGIN_REGISTRY_URL",
        "https://example.com/plugins.yaml",
    )
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
    installs: list[list[str]] = []
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)
    monkeypatch.setattr(
        plugins,
        "compute_checksum",
        lambda d, *, signature=None, public_key=None: compute_checksum(d),
    )
    monkeypatch.setattr(plugins, "verify_signature", lambda d, s, k: None)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])

    plugins.install_registry_plugins()

    assert not installs
