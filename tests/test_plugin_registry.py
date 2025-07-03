import sys
import logging

import genecoder.plugins as plugins
from genecoder.security import compute_checksum


class DummyResponse:
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._data


def test_registry_install(monkeypatch):
    installs = []

    def fake_check_call(cmd):
        installs.append(cmd)

    def fake_urlopen(url):
        assert url == "https://example.com/plugins.yaml"
        c1 = compute_checksum("pkgA>=1.0".encode())
        c2 = compute_checksum("pkgB".encode())
        data = (
            "packages:\n"
            f"  - spec: pkgA>=1.0\n    checksum: {c1}\n"
            f"  - spec: pkgB\n    checksum: {c2}"
        ).encode()
        return DummyResponse(data)

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

    plugins.install_registry_plugins()

    assert installs == [
        [sys.executable, "-m", "pip", "install", "pkgA>=1.0"],
        [sys.executable, "-m", "pip", "install", "pkgB"],
    ]


def test_registry_install_failure(monkeypatch, caplog):
    """Warnings are logged if installation of a package fails."""
    def fake_check_call(cmd):
        raise RuntimeError("boom")

    def fake_urlopen(url):
        assert url == "https://example.com/plugins.yaml"
        c1 = compute_checksum("pkgA".encode())
        data = (
            "packages:\n"
            f"  - spec: pkgA\n    checksum: {c1}"
        ).encode()

        return DummyResponse(data)

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

    with caplog.at_level(logging.WARNING):
        plugins.install_registry_plugins()

    assert "Failed to install plugin pkgA from registry" in caplog.text


def test_registry_bad_yaml(monkeypatch, caplog):
    """Malformed registry YAML triggers a warning and no installation."""

    def fake_urlopen(url):
        assert url == "https://example.com/plugins.yaml"
        return DummyResponse(b"not: [yaml")

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

    with caplog.at_level(logging.WARNING):
        plugins.install_registry_plugins()

    assert "Failed to fetch plugin registry" in caplog.text

