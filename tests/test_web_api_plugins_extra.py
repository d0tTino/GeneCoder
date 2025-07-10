from pathlib import Path
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import web.main as main
from web import plugin_catalog

main.API_TOKEN = "test-token"
client = TestClient(main.app)
AUTH_HEADERS = {"Authorization": f"Bearer {main.API_TOKEN}"}


def test_catalog_listing_and_add(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugin_catalog, "CATALOG_PATH", str(tmp_path / "cat.json"), raising=False)
    plugin_catalog.CATALOG.clear()

    r = client.get("/catalog/plugins")
    assert r.status_code == 200
    assert r.json() == {"plugins": []}

    payload = {"name": "demo", "version": "1.0", "checksum": "abc", "signature": None}
    r = client.post("/catalog/plugins", json=payload)
    assert r.status_code == 401

    r = client.post("/catalog/plugins", headers=AUTH_HEADERS, json=payload)
    assert r.status_code == 200

    r_dup = client.post("/catalog/plugins", headers=AUTH_HEADERS, json=payload)
    assert r_dup.status_code == 409

    r2 = client.get("/catalog/plugins")
    assert r2.status_code == 200
    assert r2.json()["plugins"] == [payload]


def test_rate_plugin_auth_and_invalid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    main.PLUGIN_RATINGS.clear()
    monkeypatch.setattr(main, "RATINGS_PATH", str(tmp_path / "ratings.json"), raising=False)

    r = client.post("/plugins/rate", json={"name": "demo", "rating": 5})
    assert r.status_code == 401

    r = client.post("/plugins/rate", headers=AUTH_HEADERS, json={"name": "demo", "rating": 6})
    assert r.status_code == 400

    r = client.post("/plugins/rate", headers=AUTH_HEADERS, json={"name": "demo", "rating": 4})
    assert r.status_code == 200
    assert r.json()["average"] == 4


def test_challenge_submission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugin_catalog, "CHALLENGE_PATH", str(tmp_path / "challenge.json"), raising=False)
    plugin_catalog.CHALLENGE.clear()

    r = client.get("/catalog/challenge")
    assert r.status_code == 200
    assert r.json() == {"entries": {}}

    payload = {"name": "team", "points": 5}
    r = client.post("/catalog/challenge", json=payload)
    assert r.status_code == 401

    r = client.post("/catalog/challenge", headers=AUTH_HEADERS, json=payload)
    assert r.status_code == 200

    r2 = client.get("/catalog/challenge")
    assert r2.status_code == 200
    assert r2.json()["entries"] == {"team": 5}
