import argparse
import sys
import logging
import base64
from pathlib import Path

import pytest

import genecoder.plugin_manager as plugins
from genecoder.cli import plugin as plugin_cli
from genecoder.plugin_security import compute_checksum


class DummyResponse:
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._data


def test_cli_registry_install(monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = b"PKG"
    checksum = compute_checksum(pkg)
    sig = base64.b64encode(b"sig").decode()

    def fake_urlopen(url: str) -> DummyResponse:
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkg.whl\n    checksum: {checksum}\n    signature: {sig}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    installs: list[list[str]] = []
    key = Path("/tmp/pub.pem")
    key.write_text("PUB")

    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)
    monkeypatch.setattr(
        plugins,
        "compute_checksum",
        lambda d, *, signature=None, public_key=None: compute_checksum(d),
    )
    monkeypatch.setattr(plugins, "verify_signature", lambda d, s, k: None)
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))

    plugin_cli._handle_install_registry(
        argparse.Namespace(url="https://example.com/plugins.yaml")
    )

    assert installs and installs[0][:5] == [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--require-hashes",
    ]


def test_cli_registry_install_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    pkg = b"PKG"
    checksum = compute_checksum(pkg)
    sig = base64.b64encode(b"sig").decode()

    def fake_urlopen(url: str) -> DummyResponse:
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkg.whl\n    checksum: {checksum}\n    signature: {sig}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    def fake_check_call(_cmd: list[str]) -> None:
        raise RuntimeError("boom")

    key = Path("/tmp/pub.pem")
    key.write_text("PUB")

    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(
        plugins,
        "compute_checksum",
        lambda d, *, signature=None, public_key=None: compute_checksum(d),
    )
    monkeypatch.setattr(plugins, "verify_signature", lambda d, s, k: None)
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))

    with caplog.at_level(logging.WARNING):
        plugin_cli._handle_install_registry(
            argparse.Namespace(url="https://example.com/plugins.yaml")
        )

    assert "Failed to install plugin https://example.com/pkg.whl from registry" in caplog.text


def test_cli_registry_signature_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    pkg = b"PKG"
    checksum = compute_checksum(pkg)
    sig = base64.b64encode(b"sig").decode()

    def fake_urlopen(url: str) -> DummyResponse:
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkg.whl\n    checksum: {checksum}\n    signature: {sig}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    installs: list[list[str]] = []
    key = Path("/tmp/pub.pem")
    key.write_text("PUB")

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
    monkeypatch.setattr(plugins, "verify_signature", lambda d, s, k: (_ for _ in ()).throw(ValueError("bad sig")))
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))

    with caplog.at_level(logging.ERROR), pytest.raises(SystemExit):
        plugin_cli._handle_install_registry(
            argparse.Namespace(url="https://example.com/plugins.yaml")
        )

    assert not installs
    assert "Invalid signature for plugin https://example.com/pkg.whl" in caplog.text


def test_cli_registry_checksum_mismatch(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    pkg = b"PKG"
    wrong = compute_checksum(b"WRONG")
    sig = base64.b64encode(b"sig").decode()

    def fake_urlopen(url: str) -> DummyResponse:
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkg.whl\n    checksum: {wrong}\n    signature: {sig}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    installs: list[list[str]] = []
    key = Path("/tmp/pub.pem")
    key.write_text("PUB")

    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)
    monkeypatch.setattr(
        plugins,
        "compute_checksum",
        lambda d, *, signature=None, public_key=None: compute_checksum(d),
    )
    monkeypatch.setattr(plugins, "verify_signature", lambda d, s, k: None)
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))

    with caplog.at_level(logging.WARNING):
        plugin_cli._handle_install_registry(
            argparse.Namespace(url="https://example.com/plugins.yaml")
        )

    assert not installs
    assert "Checksum mismatch for plugin https://example.com/pkg.whl" in caplog.text
