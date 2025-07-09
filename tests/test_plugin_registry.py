import sys
import logging

from typing import Callable

import pytest
httpx = pytest.importorskip("httpx")

import genecoder.plugins as plugins
from genecoder.security import compute_checksum
import base64
from pathlib import Path


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
            sig = base64.b64encode(b"sig").decode()
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkgA.whl\n    checksum: {c1}\n    signature: {sig}\n"
                f"  - spec: https://example.com/pkgB.whl\n    checksum: {c2}\n    signature: {sig}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkgA.whl":
            return DummyResponse(b"AAA")
        elif url == "https://example.com/pkgB.whl":
            return DummyResponse(b"BBB")
        raise AssertionError(url)

    key = Path("/tmp/pub.pem")
    key.write_text("PUB")
    monkeypatch.setenv(
        "GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml"
    )
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    orig_compute = plugins.compute_checksum

    def fake_compute(
        data: bytes, *, signature: bytes | None = None, public_key: bytes | None = None
    ) -> str:
        if signature is not None:
            assert signature == b"sig"
            assert public_key == b"PUB"
        return orig_compute(data)

    monkeypatch.setattr(plugins, "compute_checksum", fake_compute)

    plugins.install_registry_plugins()

    assert [cmd[:5] for cmd in installs] == [
        [sys.executable, "-m", "pip", "install", "--require-hashes"],
        [sys.executable, "-m", "pip", "install", "--require-hashes"],
    ]


def test_registry_install_failure(monkeypatch, caplog):
    def fake_check_call(cmd):
        raise RuntimeError("boom")

    def fake_urlopen(url):
        if url == "https://example.com/plugins.yaml":
            pkg = b"CCC"
            c1 = compute_checksum(pkg)
            sig = base64.b64encode(b"sig").decode()
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkgC.whl\n    checksum: {c1}\n    signature: {sig}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkgC.whl":
            return DummyResponse(b"CCC")
        raise AssertionError(url)

    key = Path("/tmp/pub.pem")
    key.write_text("PUB")
    monkeypatch.setenv(
        "GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml"
    )
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        plugins,
        "compute_checksum",
        lambda d, *, signature=None, public_key=None: compute_checksum(d),
    )

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
            sig = base64.b64encode(b"sig").decode()
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkgD.whl\n    checksum: {wrong}\n    signature: {sig}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkgD.whl":
            return DummyResponse(b"DDD")
        raise AssertionError(url)

    key = Path("/tmp/pub.pem")
    key.write_text("PUB")
    monkeypatch.setenv(
        "GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml"
    )
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        plugins,
        "compute_checksum",
        lambda d, *, signature=None, public_key=None: compute_checksum(d),
    )

    with caplog.at_level(logging.WARNING):
        plugins.install_registry_plugins()

    assert not installs
    assert "Checksum mismatch for plugin https://example.com/pkgD.whl" in caplog.text


def test_registry_signature_failure(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    pkg = b"FFF"
    checksum = compute_checksum(pkg)

    def fake_urlopen(url: str) -> DummyResponse:
        if url == "https://example.com/plugins.yaml":
            sig = base64.b64encode(b"sig").decode()
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkgF.whl\n    checksum: {checksum}\n    signature: {sig}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkgF.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    installs: list[list[str]] = []
    key = Path("/tmp/pub.pem")
    key.write_text("PUB")

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

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

    with caplog.at_level(logging.WARNING):
        plugins.install_registry_plugins()

    assert not installs
    assert "Invalid signature for plugin https://example.com/pkgF.whl" in caplog.text


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
            sig = base64.b64encode(b"sig").decode()
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkgE.whl\n    checksum: {expected}\n    signature: {sig}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkgE.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    key = Path("/tmp/pub.pem")
    key.write_text("PUB")
    monkeypatch.setenv(
        "GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml"
    )
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        plugins,
        "compute_checksum",
        lambda d, *, signature=None, public_key=None: fake_compute_checksum(d),
    )

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
            sig = base64.b64encode(b"sig").decode()
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkg.whl\n    checksum: {checksum}\n    signature: {sig}"
            )
            return httpx.Response(200, text=data)
        elif request.url.path == "/pkg.whl":
            return httpx.Response(200, content=pkg)
        raise AssertionError(request.url)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    installs: list[list[str]] = []

    key = Path("/tmp/pub.pem")
    key.write_text("PUB")
    monkeypatch.setenv(
        "GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml"
    )
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
    monkeypatch.setattr(
        plugins.urllib.request, "urlopen", _urlopen_via_httpx(client)
    )
    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)
    monkeypatch.setattr(
        plugins,
        "compute_checksum",
        lambda d, *, signature=None, public_key=None: compute_checksum(d),
    )

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
            sig = base64.b64encode(b"sig").decode()
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkg.whl\n    checksum: {wrong}\n    signature: {sig}"
            )
            return httpx.Response(200, text=data)
        elif request.url.path == "/pkg.whl":
            return httpx.Response(200, content=pkg)
        raise AssertionError(request.url)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    installs: list[list[str]] = []

    key = Path("/tmp/pub.pem")
    key.write_text("PUB")
    monkeypatch.setenv(
        "GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml"
    )
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
    monkeypatch.setattr(
        plugins.urllib.request, "urlopen", _urlopen_via_httpx(client)
    )
    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)
    monkeypatch.setattr(
        plugins,
        "compute_checksum",
        lambda d, *, signature=None, public_key=None: compute_checksum(d),
    )

    with caplog.at_level(logging.WARNING):
        plugins.install_registry_plugins()

    assert not installs
    assert "Checksum mismatch for plugin https://example.com/pkg.whl" in caplog.text
