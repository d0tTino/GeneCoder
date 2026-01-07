import base64
from pathlib import Path
import logging
import sys
import types

import pytest

import genecoder.plugin_manager as plugins


class DummyResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._data


def test_load_plugins_with_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = b"PKG"
    checksum = plugins.compute_checksum(pkg)

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                "  - spec: https://example.com/pkg.whl\n"
                "    license: MIT\n"
                f"    checksum: {checksum}\n"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])

    plugins.install_registry_plugins("https://example.com/plugins.yaml", allow_network=True)
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()

    plugins.load_plugins()

    assert "reverse" in plugins.CODEC_REGISTRY


def test_load_plugins_with_signed_registry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pkg = b"PKG"
    sig_b64 = base64.b64encode(b"sig").decode()

    key = tmp_path / "pub.pem"
    key.write_bytes(b"PUB")

    calls: list[tuple[bytes, bytes, bytes, str]] = []
    orig_compute = plugins.plugin_security.compute_checksum

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

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                "  - spec: https://example.com/pkg.whl\n"
                "    license: MIT\n"
                f"    signature: {sig_b64}\n"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])
    monkeypatch.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
    monkeypatch.setattr(plugins.plugin_security, "compute_checksum", fake_compute)

    plugins.install_registry_plugins("https://example.com/plugins.yaml", allow_network=True)
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()

    plugins.load_plugins()

    assert calls == [(pkg, b"sig", b"PUB", "pkcs1")]
    assert "reverse" in plugins.CODEC_REGISTRY


def test_registry_entry_missing_signature_checksum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                "  - spec: https://example.com/pkg.whl\n"
                "    license: MIT\n"
            ).encode()
            return DummyResponse(data)
        raise AssertionError(url)

    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)

    with pytest.raises(ValueError):
        plugins.install_registry_plugins("https://example.com/plugins.yaml", allow_network=True)


def test_registry_entry_missing_license(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                "  - spec: https://example.com/pkg.whl\n"
                "    checksum: deadbeef\n"
            ).encode()
            return DummyResponse(data)
        raise AssertionError(url)

    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)

    with pytest.raises(ValueError, match="Missing license for plugin entry https://example.com/pkg.whl"):
        plugins.install_registry_plugins("https://example.com/plugins.yaml", allow_network=True)


def test_registry_entry_disallowed_license(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                "  - spec: https://example.com/pkg.whl\n"
                "    license: Proprietary\n"
                "    checksum: deadbeef\n"
            ).encode()
            return DummyResponse(data)
        raise AssertionError(url)

    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)

    with pytest.raises(ValueError, match="Disallowed license"):
        plugins.install_registry_plugins("https://example.com/plugins.yaml", allow_network=True)


def test_entry_point_plugin_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("ep_mod")
    module.PLUGIN_METADATA = {"name": "ep-demo", "version": "1.0", "interfaces": ["codec"]}
    sys.modules["ep_mod"] = module

    class EP:
        name = "ep_mod"
        group = "genecoder.plugins"
        value = "ep_mod"

        def load(self) -> types.ModuleType:
            return module

    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [EP()] if group in (None, "genecoder.plugins") else [])
    plugins.PLUGIN_CATALOG.clear()
    plugins.load_plugin_catalog()
    assert "ep-demo" in plugins.PLUGIN_CATALOG


def test_entry_point_plugin_invalid_metadata(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    bad = types.ModuleType("bad_mod")
    bad.PLUGIN_METADATA = {"name": "bad"}  # missing fields
    sys.modules["bad_mod"] = bad

    class EPBad:
        name = "bad_mod"
        group = "genecoder.plugins"
        value = "bad_mod"

        def load(self) -> types.ModuleType:
            return bad

    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [EPBad()] if group in (None, "genecoder.plugins") else [])
    plugins.PLUGIN_CATALOG.clear()
    with caplog.at_level(logging.WARNING):
        plugins.load_plugin_catalog()
    assert "bad_mod" in caplog.text
    assert "bad" not in plugins.PLUGIN_CATALOG


def test_load_plugins_with_base64_checksum(monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = b"PKG"
    hex_digest = plugins.compute_checksum(pkg)
    checksum_b64 = base64.b64encode(bytes.fromhex(hex_digest)).decode()

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                "  - spec: https://example.com/pkg.whl\n"
                "    license: MIT\n"
                f"    checksum: {checksum_b64}\n"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)
    monkeypatch.setattr(plugins, "entry_points", lambda group=None: [])

    plugins.install_registry_plugins("https://example.com/plugins.yaml", allow_network=True)


def test_registry_base64_checksum_mismatch(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    pkg = b"PKG"
    wrong_checksum = base64.b64encode(b"WRONG").decode()

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        assert timeout == 30
        if url == "https://example.com/plugins.yaml":
            data = (
                "packages:\n"
                "  - spec: https://example.com/pkg.whl\n"
                "    license: MIT\n"
                f"    checksum: {wrong_checksum}\n"
            ).encode()
            return DummyResponse(data)
        elif url == "https://example.com/pkg.whl":
            return DummyResponse(pkg)
        raise AssertionError(url)

    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(plugins.subprocess, "check_call", lambda cmd: None)

    with pytest.raises(ValueError, match="Checksum mismatch"):
        with caplog.at_level(logging.ERROR):
            plugins.install_registry_plugins(
                "https://example.com/plugins.yaml", allow_network=True
            )
        assert "Checksum mismatch for plugin https://example.com/pkg.whl" in caplog.text
