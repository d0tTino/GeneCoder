import sys
import argparse
from pathlib import Path
import logging
import base64
import pytest


import genecoder.plugin_manager as plugins
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
    pkg = b"PKG"
    h = compute_checksum(pkg)
    catalog = (
        "plugins:\n  - name: plug\n    version: '0.1'\n    url: plug==0.1\n    description: Example\n    checksum: "
        + h
    ).encode()

    def fake_urlopen(url):
        assert url == "https://example.com/catalog.yaml"
        return DummyResponse(catalog)

    installs = []
    calls = []

    def fake_check_call(cmd):
        if cmd[:4] == [sys.executable, "-m", "pip", "download"]:
            dest = cmd[cmd.index("-d") + 1]
            Path(dest).mkdir(parents=True, exist_ok=True)
            (Path(dest) / "plug.whl").write_bytes(pkg)
        elif cmd[:4] == [sys.executable, "-m", "pip", "install"]:
            installs.append(cmd)
        else:
            raise AssertionError(cmd)

    def fake_compute_checksum(data: bytes) -> str:
        calls.append(data)
        return compute_checksum(data)

    monkeypatch.setenv("GENECODER_PLUGIN_CATALOG_URL", "https://example.com/catalog.yaml")
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins, "compute_checksum", fake_compute_checksum)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])

    plugins.load_plugins()
    assert "plug" in plugins.PLUGIN_CATALOG

    plugin_cli._handle_list(argparse.Namespace())
    captured = capsys.readouterr().out
    assert "plug" in captured

    plugin_cli._handle_install(argparse.Namespace(name="plug"))
    assert installs and installs[0][:4] == [sys.executable, "-m", "pip", "install"]
    assert calls == [pkg]


def test_install_checksum_mismatch(monkeypatch, caplog):
    pkg = b"PKG"
    wrong = compute_checksum(b"WRONG")
    catalog = (
        "plugins:\n  - name: plug\n    version: '0.1'\n    url: plug==0.1\n    checksum: "
        + wrong
    ).encode()

    def fake_urlopen(url):
        assert url == "https://example.com/catalog.yaml"
        return DummyResponse(catalog)

    installs = []

    def fake_check_call(cmd):
        if cmd[:4] == [sys.executable, "-m", "pip", "download"]:
            dest = cmd[cmd.index("-d") + 1]
            Path(dest).mkdir(parents=True, exist_ok=True)
            (Path(dest) / "plug.whl").write_bytes(pkg)
        elif cmd[:4] == [sys.executable, "-m", "pip", "install"]:
            installs.append(cmd)
        else:
            raise AssertionError(cmd)

    monkeypatch.setenv("GENECODER_PLUGIN_CATALOG_URL", "https://example.com/catalog.yaml")
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])

    plugins.load_plugins()

    with caplog.at_level("WARNING"), pytest.raises(SystemExit):
        plugin_cli._handle_install(argparse.Namespace(name="plug"))

    assert not installs
    assert "Checksum mismatch for plugin plug" in caplog.text


def test_install_signature_mismatch(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    pkg = b"PKG"
    checksum = compute_checksum(pkg)
    sig = base64.b64encode(b"sig").decode()

    catalog = (
        "plugins:\n"
        "  - name: plug\n"
        "    version: '0.1'\n"
        "    url: plug==0.1\n"
        f"    checksum: {checksum}\n"
        f"    signature: {sig}"
    ).encode()

    def fake_urlopen(url: str) -> DummyResponse:
        assert url == "https://example.com/catalog.yaml"
        return DummyResponse(catalog)

    installs: list[list[str]] = []

    def fake_check_call(cmd: list[str]) -> None:
        if cmd[:4] == [sys.executable, "-m", "pip", "download"]:
            dest = cmd[cmd.index("-d") + 1]
            Path(dest).mkdir(parents=True, exist_ok=True)
            (Path(dest) / "plug.whl").write_bytes(pkg)
        elif cmd[:4] == [sys.executable, "-m", "pip", "install"]:
            installs.append(cmd)
        else:  # pragma: no cover - unexpected command
            raise AssertionError(cmd)

    key = Path("/tmp/pub.pem")
    key.write_text("PUB")

    monkeypatch.setenv("GENECODER_PLUGIN_CATALOG_URL", "https://example.com/catalog.yaml")
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])

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

    plugins.load_plugins()

    with caplog.at_level(logging.ERROR), pytest.raises(SystemExit):
        plugin_cli._handle_install(argparse.Namespace(name="plug"))

    assert not installs
    assert "Signature verification failed for plugin plug" in caplog.text


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

