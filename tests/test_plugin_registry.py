import sys
import logging
import subprocess

from typing import Callable
from pathlib import Path
import base64

import pytest

httpx = pytest.importorskip("httpx")

import genecoder.plugin_manager as plugins


class DummyResponse:
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._data


def test_registry_install(monkeypatch: pytest.MonkeyPatch) -> None:
    installs: list[list[str]] = []
    pkg = b"PKG"
    checksum = plugins.compute_checksum(pkg)

    def fake_check_call(cmd: list[str]) -> None:
        installs.append(cmd)

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkgA.whl\n    checksum: {checksum}\n"
                f"  - spec: https://example.com/pkgB.whl\n    checksum: {checksum}\n"
            ).encode()
            return DummyResponse(data)
        elif url in ("https://example.com/pkgA.whl", "https://example.com/pkgB.whl"):
            return DummyResponse(pkg)
        raise AssertionError(url)

    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

    plugins.install_registry_plugins("https://example.com/plugins.yaml")

    assert len(installs) == 2
    for cmd in installs:
        assert cmd[:4] == [sys.executable, "-m", "pip", "install"]


def test_registry_install_failure(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    def fake_check_call(cmd: list[str]) -> None:
        raise RuntimeError("boom")

    pkg = b"PKG"
    checksum = plugins.compute_checksum(pkg)

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkgC.whl\n    checksum: {checksum}\n"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkgC.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

    with caplog.at_level(logging.WARNING):
        plugins.install_registry_plugins("https://example.com/plugins.yaml")

    assert "Failed to install plugin https://example.com/pkgC.whl from registry" in caplog.text


def test_registry_bad_yaml(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        assert url == "https://example.com/plugins.yaml"
        return DummyResponse(b"not: [yaml")

    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

    with caplog.at_level(logging.WARNING), pytest.raises(ValueError):
        plugins.install_registry_plugins("https://example.com/plugins.yaml")

    assert "Failed to parse plugin registry" in caplog.text


def test_registry_unreachable(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        raise OSError("no network")

    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

    with caplog.at_level(logging.WARNING):
        plugins.install_registry_plugins("https://example.com/plugins.yaml")

    assert "Failed to fetch plugin registry" in caplog.text


def test_registry_install_offline_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_path = tmp_path / "pkg.whl"
    pkg_bytes = b"PKG"
    pkg_path.write_bytes(pkg_bytes)
    checksum = plugins.compute_checksum(pkg_bytes)

    registry = tmp_path / "registry.yaml"
    registry.write_text(
        "packages:\n  - spec: {pkg}\n    checksum: {chk}\n".format(
            pkg=pkg_path.as_uri(), chk=checksum
        )
    )

    installs: list[list[str]] = []

    def fake_urlopen(*args, **kwargs):  # pragma: no cover - should not be used
        raise AssertionError("network access attempted")

    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)

    plugins.install_registry_plugins(str(registry), offline=True)

    assert installs and installs[0][:4] == [
        sys.executable,
        "-m",
        "pip",
        "install",
    ]


def test_registry_offline_remote_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    with pytest.raises(RuntimeError, match="Offline mode forbids fetching registry"):
        plugins.install_registry_plugins("https://example.com/plugins.yaml", offline=True)


def _urlopen_via_httpx(client: httpx.Client) -> Callable[[str], DummyResponse]:
    """Return a urlopen replacement using ``client``."""

    def _open(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        resp = client.get(url)
        return DummyResponse(resp.content)

    return _open


def test_registry_install_via_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = b"PKG"
    checksum = plugins.compute_checksum(pkg)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/plugins.yaml":
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkg.whl\n    checksum: {checksum}\n"
            )
            return httpx.Response(200, text=data)
        elif request.url.path == "/pkg.whl":
            return httpx.Response(200, content=pkg)
        raise AssertionError(request.url)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    installs: list[list[str]] = []

    monkeypatch.setattr(plugins.urllib.request, "urlopen", _urlopen_via_httpx(client))
    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)

    plugins.install_registry_plugins("https://example.com/plugins.yaml")

    assert installs and installs[0][:4] == [
        sys.executable,
        "-m",
        "pip",
        "install",
    ]


def test_catalog_signature_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Path("/tmp/pub.pem")
    key.write_text("PUB")

    sig_b64 = base64.b64encode(b"sig").decode()
    calls: list[tuple[bytes, bytes, bytes, str]] = []

    orig_compute = plugins.compute_checksum

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


    monkeypatch.setenv("GENECODER_CATALOG_PUBLIC_KEY", str(key))
    monkeypatch.setattr(plugins, "compute_checksum", fake_compute)

    assert plugins._verify_catalog_signature(b"DATA", sig_b64, padding_scheme="pss")
    assert calls == [(b"DATA", b"sig", b"PUB", "pss")]


def test_registry_network_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def fake_check_call(cmd: list[str]) -> None:
        raise subprocess.CalledProcessError(1, cmd, "network unreachable")

    pkg = b"PKG"
    checksum = plugins.compute_checksum(pkg)

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                f"  - spec: https://example.com/pkgD.whl\n    checksum: {checksum}\n"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkgD.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    class FakeYAML:
        @staticmethod
        def safe_load(raw: bytes) -> dict[str, list[dict[str, str]]]:
            return {"packages": [{"spec": "https://example.com/pkgD.whl", "checksum": checksum}]}

    monkeypatch.setattr(plugins.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins, "yaml", FakeYAML)

    with caplog.at_level(logging.WARNING):
        plugins.install_registry_plugins("https://example.com/plugins.yaml")

    assert (
        "Failed to install plugin https://example.com/pkgD.whl from registry" in caplog.text
    )


def test_registry_version_match(monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = b"PKG"

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = Path("tests/data/plugin_registry_version.yaml").read_bytes()
            return DummyResponse(data)
        elif url == "example_pkg":
            return DummyResponse(pkg)
        raise AssertionError(url)

    installs: list[list[str]] = []

    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins, "get_pkg_version", lambda name: "1.0.0")

    plugins.install_registry_plugins("https://example.com/plugins.yaml")

    assert installs and installs[0][:4] == [sys.executable, "-m", "pip", "install"]


def test_registry_version_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = b"PKG"

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = Path("tests/data/plugin_registry_version.yaml").read_bytes()
            return DummyResponse(data)
        elif url == "example_pkg":
            return DummyResponse(pkg)
        raise AssertionError(url)

    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins, "get_pkg_version", lambda name: "0.9.0")

    with pytest.raises(ValueError, match="Version mismatch"):
        plugins.install_registry_plugins("https://example.com/plugins.yaml")
