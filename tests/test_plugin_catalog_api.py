from pathlib import Path
import json
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


def test_plugin_rating(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugin_catalog, "CATALOG_PATH", str(tmp_path / "cat.json"), raising=False)
    plugin_catalog.CATALOG.clear()
    plugin_catalog.PLUGIN_RATINGS.clear()

    payload = {"name": "demo", "version": "1.0", "checksum": "abc", "signature": None}
    r = client.post("/catalog/plugins", headers=AUTH_HEADERS, json=payload)
    assert r.status_code == 200

    r = client.post(
        "/catalog/plugins/rate",
        headers=AUTH_HEADERS,
        json={"name": "demo", "rating": 5},
    )
    assert r.status_code == 200
    assert r.json()["average"] == 5

    path = tmp_path / "cat.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["ratings"]["demo"] == [5]

