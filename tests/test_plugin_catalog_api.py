from pathlib import Path
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import web.main as main
from web import plugin_catalog

main.API_TOKEN = "test-token"
client = TestClient(main.app)
AUTH_HEADERS = {"Authorization": f"Bearer {main.API_TOKEN}"}


def test_add_plugin_requires_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugin_catalog, "CATALOG_PATH", str(tmp_path / "cat.json"), raising=False)
    plugin_catalog.CATALOG.clear()

    payload = {"name": "demo", "version": "1.0", "checksum": "abc", "signature": "sig"}
    r = client.post("/catalog/plugins", json=payload)
    assert r.status_code == 401
    assert plugin_catalog.CATALOG == []


def test_add_plugin_missing_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugin_catalog, "CATALOG_PATH", str(tmp_path / "cat.json"), raising=False)
    plugin_catalog.CATALOG.clear()

    payload = {"name": "demo", "version": "1.0"}
    r = client.post("/catalog/plugins", headers=AUTH_HEADERS, json=payload)
    assert r.status_code == 422
    assert plugin_catalog.CATALOG == []


def test_add_plugin_invalid_signature(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugin_catalog, "CATALOG_PATH", str(tmp_path / "cat.json"), raising=False)
    plugin_catalog.CATALOG.clear()

    payload = {"name": "demo", "version": "1.0", "checksum": "abc", "signature": 123}
    r = client.post("/catalog/plugins", headers=AUTH_HEADERS, json=payload)
    assert r.status_code == 422
    assert plugin_catalog.CATALOG == []

