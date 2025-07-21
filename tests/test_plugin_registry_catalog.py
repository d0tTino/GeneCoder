import sys
import base64
from pathlib import Path
from typing import Literal
import types
import os

portalocker_stub = types.ModuleType("portalocker")
portalocker_stub.Lock = lambda *a, **k: open(os.devnull, "w")  # type: ignore[attr-defined]
sys.modules.setdefault("portalocker", portalocker_stub)

import pytest
pytest.importorskip("yaml")
import genecoder.plugin_manager as plugins
from genecoder.plugin_security import compute_checksum


class DummyResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def __enter__(self) -> "DummyResponse":
        return self

    def __exit__(self, *exc: object) -> "Literal[False]":
        return False

    def read(self) -> bytes:
        return self._data


def test_registry_and_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = b"PKG"
    checksum = compute_checksum(pkg)
    sig = base64.b64encode(b"sig").decode()

    registry_yaml = (
        "packages:\n"
        f"  - spec: https://example.com/pkg.whl\n    checksum: {checksum}\n    signature: {sig}"
    ).encode()

    catalog_yaml = (
        "plugins:\n"
        "  - name: plug\n"
        "    version: '0.1'\n"
        "    url: https://example.com/pkg.whl\n"
        f"    checksum: {checksum}\n"
        f"    signature: {sig}"
    ).encode()

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            return DummyResponse(registry_yaml)
        if url == "https://example.com/catalog.yaml":
            return DummyResponse(catalog_yaml)
        if url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    installs: list[list[str]] = []

    def fake_check_call(cmd: list[str]) -> None:
        if cmd[:4] == [sys.executable, "-m", "pip", "download"]:
            dest = cmd[cmd.index("-d") + 1]
            Path(dest).mkdir(parents=True, exist_ok=True)
            (Path(dest) / "pkg.whl").write_bytes(pkg)
        elif cmd[:4] == [sys.executable, "-m", "pip", "install"]:
            installs.append(cmd)
        else:
            raise AssertionError(cmd)

    key = Path("/tmp/pub.pem")
    key.write_text("PUB")
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setenv("GENECODER_PLUGIN_CATALOG_URL", "https://example.com/catalog.yaml")
    monkeypatch.setenv("GENECODER_CATALOG_PUBLIC_KEY", str(key))
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(
        plugins,
        "compute_checksum",
        lambda d, *, signature=None, public_key=None: compute_checksum(d),
    )
    monkeypatch.setattr(plugins, "verify_signature", lambda d, s, k: None)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])

    plugins.install_registry_plugins()
    plugins.load_plugins()

    assert installs and installs[0][:4] == [sys.executable, "-m", "pip", "install"]
    assert "plug" in plugins.PLUGIN_CATALOG
