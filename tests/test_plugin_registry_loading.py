import base64
from pathlib import Path

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


def test_load_plugins_with_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = b"PKG"
    checksum = plugins.compute_checksum(pkg)

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

    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])

    plugins.install_registry_plugins("https://example.com/plugins.yaml")
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()

    plugins.load_plugins()

    assert "reverse" in plugins.CODEC_REGISTRY


def test_load_plugins_with_signed_registry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pkg = b"PKG"
    sig_b64 = base64.b64encode(b"sig").decode()

    key = tmp_path / "pub.pem"
    key.write_bytes(b"PUB")

    calls: list[tuple[bytes, bytes, bytes, str]] = []
    orig_compute = plugins.plugin_security.compute_checksum

    def fake_compute(
        data: bytes,
        *,
        signature: bytes | None = None,
        public_key: bytes | None = None,
        padding_scheme: str = "pkcs1",
    ) -> str:
        assert signature is not None and public_key is not None
        calls.append((data, signature, public_key, padding_scheme))
        return orig_compute(data)

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkg.whl\n    signature: {sig_b64}\n"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
    monkeypatch.setattr(plugins.plugin_security, "compute_checksum", fake_compute)

    plugins.install_registry_plugins("https://example.com/plugins.yaml")
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()

    plugins.load_plugins()

    assert calls == [(pkg, b"sig", b"PUB", "pkcs1")]
    assert "reverse" in plugins.CODEC_REGISTRY


def test_registry_entry_missing_signature_checksum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = "packages:\n  - spec: https://example.com/pkg.whl\n".encode()
            return DummyResponse(data)
        raise AssertionError(url)

    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)

    with pytest.raises(ValueError):
        plugins.install_registry_plugins("https://example.com/plugins.yaml")
