import sys
import logging

from typing import Callable

import httpx
import pytest

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
        if url == "https://example.com/plugins.yaml":
            pkg_a = b"AAA"
            pkg_b = b"BBB"
            c1 = compute_checksum(pkg_a)
            c2 = compute_checksum(pkg_b)
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkgA.whl\n    checksum: {c1}\n"
                f"  - spec: https://example.com/pkgB.whl\n    checksum: {c2}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkgA.whl":
            return DummyResponse(b"AAA")
        elif url == "https://example.com/pkgB.whl":
            return DummyResponse(b"BBB")
        raise AssertionError(url)

    monkeypatch.setenv(
        "GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml"
    )
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

    plugins.install_registry_plugins()

    assert [cmd[:4] for cmd in installs] == [
        [sys.executable, "-m", "pip", "install"],
        [sys.executable, "-m", "pip", "install"],
    ]


def test_registry_install_failure(monkeypatch, caplog):
    def fake_check_call(cmd):
        raise RuntimeError("boom")

    def fake_urlopen(url):
        if url == "https://example.com/plugins.yaml":
            pkg = b"CCC"
            c1 = compute_checksum(pkg)
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkgC.whl\n    checksum: {c1}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkgC.whl":
            return DummyResponse(b"CCC")
        raise AssertionError(url)

    monkeypatch.setenv(
        "GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml"
    )
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

    with caplog.at_level(logging.WARNING):
        plugins.install_registry_plugins()

    assert (
        "Failed to install plugin https://example.com/pkgC.whl from registry"
        in caplog.text
    )


def test_registry_bad_yaml(monkeypatch, caplog):
    def fake_urlopen(url):
        assert url == "https://example.com/plugins.yaml"
        return DummyResponse(b"not: [yaml")

    monkeypatch.setenv(
        "GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml"
    )
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

    with caplog.at_level(logging.WARNING):
        plugins.install_registry_plugins()

    assert "Failed to fetch plugin registry" in caplog.text


def test_registry_checksum_mismatch(monkeypatch, caplog):
    installs = []

    def fake_check_call(cmd):
        installs.append(cmd)

    def fake_urlopen(url):
        if url == "https://example.com/plugins.yaml":
            wrong = compute_checksum(b"WRONG")
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkgD.whl\n    checksum: {wrong}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkgD.whl":
            return DummyResponse(b"DDD")
        raise AssertionError(url)

    monkeypatch.setenv(
        "GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml"
    )
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

    with caplog.at_level(logging.WARNING):
        plugins.install_registry_plugins()

    assert not installs
    assert "Checksum mismatch for plugin https://example.com/pkgD.whl" in caplog.text


def test_registry_checksum_validation(monkeypatch):
    """The checksum is computed from the downloaded package bytes."""
    pkg = b"EEE"
    expected = compute_checksum(pkg)
    calls: list[bytes] = []

    orig_compute = compute_checksum

    def fake_compute_checksum(data: bytes) -> str:
        calls.append(data)
        return orig_compute(data)

    def fake_urlopen(url):
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkgE.whl\n    checksum: {expected}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkgE.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    monkeypatch.setenv(
        "GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml"
    )
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins, "compute_checksum", fake_compute_checksum)

    plugins.install_registry_plugins()

    assert calls == [pkg]


def _urlopen_via_httpx(client: httpx.Client) -> Callable[[str], DummyResponse]:
    """Return a urlopen replacement using ``client``."""

    def _open(url: str) -> DummyResponse:
        resp = client.get(url)
        return DummyResponse(resp.content)

    return _open


def test_registry_install_via_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plugins are installed when checksums match using ``httpx``."""

    pkg = b"PKG"
    checksum = compute_checksum(pkg)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/plugins.yaml":
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkg.whl\n    checksum: {checksum}"
            )
            return httpx.Response(200, text=data)
        elif request.url.path == "/pkg.whl":
            return httpx.Response(200, content=pkg)
        raise AssertionError(request.url)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    installs: list[list[str]] = []

    monkeypatch.setenv(
        "GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml"
    )
    monkeypatch.setattr(
        plugins.urllib.request, "urlopen", _urlopen_via_httpx(client)
    )
    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)

    plugins.install_registry_plugins()

    assert installs and installs[0][:4] == [
        sys.executable,
        "-m",
        "pip",
        "install",
    ]


def test_registry_install_via_httpx_checksum_mismatch(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Installation is refused when the checksum does not match."""

    pkg = b"PKG"
    wrong = compute_checksum(b"WRONG")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/plugins.yaml":
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkg.whl\n    checksum: {wrong}"
            )
            return httpx.Response(200, text=data)
        elif request.url.path == "/pkg.whl":
            return httpx.Response(200, content=pkg)
        raise AssertionError(request.url)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    installs: list[list[str]] = []

    monkeypatch.setenv(
        "GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml"
    )
    monkeypatch.setattr(
        plugins.urllib.request, "urlopen", _urlopen_via_httpx(client)
    )
    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)

    with caplog.at_level(logging.WARNING):
        plugins.install_registry_plugins()

    assert not installs
    assert "Checksum mismatch for plugin https://example.com/pkg.whl" in caplog.text
