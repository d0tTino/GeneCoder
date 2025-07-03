import sys
import argparse

import genecoder.plugins as plugins
from genecoder.cli import plugin as plugin_cli


class DummyResponse:
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._data


def test_catalog_list_and_install(monkeypatch, capsys):
    catalog = b"plugins:\n  - name: plug\n    version: '0.1'\n    url: plug==0.1\n    description: Example"

    def fake_urlopen(url):
        assert url == "https://example.com/catalog.yaml"
        return DummyResponse(catalog)

    installs = []

    def fake_check_call(cmd):
        installs.append(cmd)

    monkeypatch.setenv("GENECODER_PLUGIN_CATALOG_URL", "https://example.com/catalog.yaml")
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])

    plugins.load_plugins()
    assert "plug" in plugins.PLUGIN_CATALOG

    plugin_cli._handle_list(argparse.Namespace())
    captured = capsys.readouterr().out
    assert "plug" in captured

    plugin_cli._handle_install(argparse.Namespace(name="plug"))
    assert installs == [[sys.executable, "-m", "pip", "install", "plug==0.1"]]


def test_catalog_network_error(monkeypatch, caplog):
    """Network failures fetching the catalog are logged as warnings."""

    def fake_urlopen(url):
        raise RuntimeError("offline")

    monkeypatch.setenv("GENECODER_PLUGIN_CATALOG_URL", "https://example.com/catalog.yaml")
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])

    plugins.PLUGIN_CATALOG.clear()

    with caplog.at_level("WARNING"):
        plugins.load_plugins()

    assert "Failed to fetch plugin catalog" in caplog.text
    assert plugins.PLUGIN_CATALOG == {}


def test_catalog_invalid_signature(monkeypatch, caplog):
    """Invalid catalog signatures are logged and ignored."""

    catalog = b"plugins:\n  - name: bad\n    version: '0.1'\n    url: bad==0.1\n    description: Bad\nsignature: wrong"

    def fake_urlopen(url):
        assert url == "https://example.com/catalog.yaml"
        return DummyResponse(catalog)

    monkeypatch.setenv("GENECODER_PLUGIN_CATALOG_URL", "https://example.com/catalog.yaml")
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])
    monkeypatch.setattr(plugins, "_verify_catalog_signature", lambda data, sig: False)

    plugins.PLUGIN_CATALOG.clear()

    with caplog.at_level("WARNING"):
        plugins.load_plugins()

    assert "Invalid catalog signature" in caplog.text
    assert plugins.PLUGIN_CATALOG == {}
