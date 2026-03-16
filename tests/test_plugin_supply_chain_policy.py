from __future__ import annotations

import base64
import pytest

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


def test_policy_offline_blocks_remote_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    with pytest.raises(RuntimeError, match="Network access is disabled"):
        plugins.install_registry_plugins(offline=True, allow_network=True)


def test_policy_requires_trust_root(monkeypatch: pytest.MonkeyPatch) -> None:
    checksum = compute_checksum(b"PKG")
    signature = base64.b64encode(b"sig").decode()

    def fake_urlopen(url: str, *, timeout: int | None = None) -> DummyResponse:
        if url.endswith("plugins.yaml"):
            return DummyResponse(
                (
                    "packages:\n"
                    "  - spec: https://example.com/pkg.whl\n"
                    "    license: MIT\n"
                    f"    checksum: {checksum}\n"
                    f"    signature: {signature}\n"
                    "    provenance_publisher: test-publisher\n"
                    "    provenance_channel: stable\n"
                ).encode()
            )
        return DummyResponse(b"PKG")

    monkeypatch.setenv("GENECODER_PLUGIN_REGISTRY_URL", "https://example.com/plugins.yaml")
    monkeypatch.delenv("GENECODER_PLUGIN_PUBLIC_KEY", raising=False)
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(ValueError, match="Invalid signature"):
        plugins.install_registry_plugins(allow_network=True)


def test_policy_license_allowlist_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = (
        "packages:\n"
        "  - spec: file:///tmp/pkg.whl\n"
        "    license: Proprietary\n"
        "    checksum: deadbeef\n"
        "    signature: AAAA\n"
    ).encode()

    monkeypatch.setattr(plugins.urllib.request, "urlopen", lambda url, timeout=30: DummyResponse(registry))

    with pytest.raises(ValueError, match="Disallowed license"):
        plugins.install_registry_plugins("https://example.com/plugins.yaml", allow_network=True)


def test_policy_requires_provenance_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    checksum = compute_checksum(b"PKG")
    signature = base64.b64encode(b"sig").decode()

    registry = (
        "packages:\n"
        "  - spec: file:///tmp/pkg.whl\n"
        "    license: MIT\n"
        f"    checksum: {checksum}\n"
        f"    signature: {signature}\n"
    ).encode()

    monkeypatch.setattr(plugins.urllib.request, "urlopen", lambda url, timeout=30: DummyResponse(registry))

    with pytest.raises(ValueError, match="Missing provenance_publisher"):
        plugins.install_registry_plugins("https://example.com/plugins.yaml", allow_network=True)
