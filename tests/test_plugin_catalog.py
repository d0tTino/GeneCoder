import pytest
from pathlib import Path

pytest.importorskip("fastapi_limiter")
fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import web.main as main


def test_challenge_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GENECODER_API_TOKEN", "tok")
    challenge_file = tmp_path / "challenge_data.json"
    monkeypatch.setattr(main.plugin_catalog, "CHALLENGE_PATH", challenge_file, raising=False)
    if hasattr(main.plugin_catalog, "_challenge"):
        main.plugin_catalog._challenge = None

    client = TestClient(main.app)
    r = client.get("/catalog/challenge")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    data = r.json()
    assert isinstance(data, dict)
    assert "entries" in data
    assert isinstance(data["entries"], dict)
