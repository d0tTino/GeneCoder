import base64
import sys
from pathlib import Path
import logging

import pytest

pytest.importorskip("portalocker")
pytest.importorskip("yaml")

import genecoder.plugin_manager as plugins
from genecoder.plugin_security import compute_checksum


class DummyResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._data


def test_registry_invalid_signature(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    pkg = b"PKG"
    checksum = compute_checksum(pkg)
    sig_b64 = base64.b64encode(b"sig").decode()

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                "  - spec: https://example.com/pkg.whl\n"
                "    license: MIT\n"
                f"    checksum: {checksum}\n"
                f"    signature: {sig_b64}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    installs: list[list[str]] = []
    key = Path("/tmp/pub.pem")
    key.write_text("PUB")

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
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

    with pytest.raises(ValueError, match="Invalid signature"):
        with caplog.at_level(logging.ERROR):
            plugins.install_registry_plugins()

    assert not installs
    assert "Invalid signature for plugin https://example.com/pkg.whl" in caplog.text


def test_registry_valid_checksum_and_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = b"PKG"
    checksum = compute_checksum(pkg)
    sig_b64 = base64.b64encode(b"sig").decode()

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                "  - spec: https://example.com/pkg.whl\n"
                "    license: MIT\n"
                f"    checksum: {checksum}\n"
                f"    signature: {sig_b64}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    installs: list[list[str]] = []
    key = Path("/tmp/pub.pem")
    key.write_text("PUB")

    def fake_compute(
        data: bytes,
        *,
        signature: bytes | None = None,
        public_key: bytes | None = None,
    ) -> str:
        assert signature == b"sig"
        assert public_key == b"PUB"
        return compute_checksum(data)

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)
    monkeypatch.setattr(plugins, "compute_checksum", fake_compute)

    plugins.install_registry_plugins()

    assert installs and installs[0][:4] == [sys.executable, "-m", "pip", "install"]


def test_registry_checksum_mismatch(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    pkg = b"PKG"
    wrong_checksum = "deadbeef"

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                "  - spec: https://example.com/pkg.whl\n"
                "    license: MIT\n"
                f"    checksum: {wrong_checksum}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    installs: list[list[str]] = []

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)

    with pytest.raises(ValueError, match="Checksum mismatch"):
        with caplog.at_level(logging.ERROR):
            plugins.install_registry_plugins()

    assert not installs
    assert "Checksum mismatch for plugin https://example.com/pkg.whl" in caplog.text


def test_registry_missing_checksum_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        assert url == "https://example.com/plugins.yaml"
        data = (
            "packages:\n"
            "  - spec: https://example.com/pkg.whl\n"
            "    license: MIT\n"
        ).encode()
        return DummyResponse(data)

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)

    with pytest.raises(ValueError, match="Signed metadata and checksum are required"):
        plugins.install_registry_plugins()


def _plugin_data_paths() -> tuple[Path, Path, str]:
    root = Path(__file__).resolve().parent
    pkg = root / "data" / "plugins" / "fake_pkg.whl"
    sig_b64 = (root / "data" / "plugins" / "fake_sig.b64").read_text().strip()
    pub = root / "data" / "plugins" / "fake_pub.pem"
    return pkg, pub, sig_b64


def test_registry_real_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_path, pub_key, sig_b64 = _plugin_data_paths()
    pkg_bytes = pkg_path.read_bytes()
    checksum = compute_checksum(pkg_bytes)

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                "  - spec: https://example.com/pkg.whl\n"
                "    license: MIT\n"
                f"    checksum: {checksum}\n"
                f"    signature: {sig_b64}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg_bytes)
        raise AssertionError(url)

    installs: list[list[str]] = []

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(pub_key))
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)

    plugins.install_registry_plugins()

    assert installs and installs[0][:4] == [sys.executable, "-m", "pip", "install"]


def test_registry_real_invalid_signature(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    pkg_path, pub_key, _sig_b64 = _plugin_data_paths()
    pkg_bytes = pkg_path.read_bytes()
    checksum = compute_checksum(pkg_bytes)
    bad_sig_b64 = "AAAA"

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                "  - spec: https://example.com/pkg.whl\n"
                "    license: MIT\n"
                f"    checksum: {checksum}\n"
                f"    signature: {bad_sig_b64}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg_bytes)
        raise AssertionError(url)

    installs: list[list[str]] = []

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(pub_key))
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)

    with pytest.raises(ValueError, match="Invalid signature"):
        with caplog.at_level(logging.ERROR):
            plugins.install_registry_plugins()

    assert not installs
    assert "Invalid signature for plugin https://example.com/pkg.whl" in caplog.text


def test_registry_real_checksum_mismatch(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    pkg_path, pub_key, sig_b64 = _plugin_data_paths()
    pkg_bytes = pkg_path.read_bytes()
    wrong_checksum = "deadbeef"

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                "  - spec: https://example.com/pkg.whl\n"
                "    license: MIT\n"
                f"    checksum: {wrong_checksum}\n"
                f"    signature: {sig_b64}"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg_bytes)
        raise AssertionError(url)

    installs: list[list[str]] = []

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(pub_key))
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", installs.append)

    with pytest.raises(ValueError, match="Checksum mismatch"):
        with caplog.at_level(logging.ERROR):
            plugins.install_registry_plugins()

    assert not installs
    assert "Checksum mismatch for plugin https://example.com/pkg.whl" in caplog.text
