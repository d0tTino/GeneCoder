import json
from pathlib import Path
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import web.main as main
from web import plugin_catalog

main.API_TOKEN = "test-token"
client = TestClient(main.app)
AUTH_HEADERS = {"Authorization": f"Bearer {main.API_TOKEN}"}


def test_challenge_persistence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugin_catalog, "CHALLENGE_PATH", str(tmp_path / "challenge.json"), raising=False)
    plugin_catalog.CHALLENGE.clear()

    r = client.get("/catalog/challenge")
    assert r.status_code == 200
    assert r.json() == {"entries": {}}

    payload = {"name": "team", "points": 7}
    r = client.post("/catalog/challenge", headers=AUTH_HEADERS, json=payload)
    assert r.status_code == 200

    data = json.loads((tmp_path / "challenge.json").read_text())
    assert data == {"team": 7}

    plugin_catalog.CHALLENGE.clear()
    plugin_catalog._load_challenge()

    assert plugin_catalog.CHALLENGE == {"team": 7}

    r2 = client.get("/catalog/challenge")
    assert r2.status_code == 200
    assert r2.json()["entries"] == {"team": 7}


def test_challenge_accumulates_points(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugin_catalog, "CHALLENGE_PATH", str(tmp_path / "c.json"), raising=False)
    plugin_catalog.CHALLENGE.clear()

    payload = {"name": "team", "points": 2}
    r = client.post("/catalog/challenge", headers=AUTH_HEADERS, json=payload)
    assert r.status_code == 200

    payload2 = {"name": "team", "points": 3}
    r = client.post("/catalog/challenge", headers=AUTH_HEADERS, json=payload2)
    assert r.status_code == 200

    assert plugin_catalog.CHALLENGE["team"] == 5
