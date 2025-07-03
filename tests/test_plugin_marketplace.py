import sys
import argparse
import logging
import pytest

import genecoder.plugins as plugins
from genecoder.cli import plugin as plugin_cli
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


def test_catalog_list_and_install(monkeypatch, capsys):
    h = compute_checksum("plug==0.1".encode())
    catalog = (
        "plugins:\n  - name: plug\n    version: '0.1'\n    url: plug==0.1\n    description: Example\n    checksum: "
        + h
    ).encode()

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


def test_install_checksum_mismatch(monkeypatch, caplog):
    catalog = (
        "plugins:\n  - name: plug\n    version: '0.1'\n    url: plug==0.1\n    description: Example\n    checksum: wrong"
    ).encode()

    def fake_urlopen(url):
        assert url == "https://example.com/catalog.yaml"
        return DummyResponse(catalog)

    monkeypatch.setenv("GENECODER_PLUGIN_CATALOG_URL", "https://example.com/catalog.yaml")
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])

    plugins.load_plugins()
    with caplog.at_level(logging.WARNING):
        with pytest.raises(SystemExit):
            plugin_cli._handle_install(argparse.Namespace(name="plug"))
    assert "checksum mismatch" in caplog.text.lower()
