import sys
import logging

import builtins
import genecoder.plugins as plugins


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
        data = b"packages:\n  - pkgA>=1.0\n  - pkgB"
        return DummyResponse(data)

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(builtins, "input", lambda _: "y")

    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()

    plugins.load_plugins()

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
        data = b"packages:\n  - pkgA"

        return DummyResponse(data)

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

    with caplog.at_level(logging.WARNING):
        plugins.load_plugins()

    assert "Failed to install plugin pkgA from registry" in caplog.text


def test_registry_bad_yaml(monkeypatch, caplog):
    """Malformed registry YAML triggers a warning and no installation."""

    def fake_urlopen(url):
        assert url == "https://example.com/plugins.yaml"
        return DummyResponse(b"not: [yaml")

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

    with caplog.at_level(logging.WARNING):
        plugins.load_plugins()

    assert "Failed to fetch plugin registry" in caplog.text

