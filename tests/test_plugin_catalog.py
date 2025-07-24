import json
import logging
from pathlib import Path

import pytest

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


def test_load_catalog_signature(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import genecoder.plugin_manager as plugins

    catalog = {"plugins": {"demo": {"description": "Demo"}}, "signature": "sig"}
    path = tmp_path / "cat.json"
    path.write_text(json.dumps(catalog))

    calls: list[tuple[bytes, str]] = []

    def fake_verify(data: bytes, sig: str) -> bool:
        calls.append((data, sig))
        return True

    monkeypatch.setattr(plugins, "_verify_catalog_signature", fake_verify)
    plugins.PLUGIN_CATALOG.clear()
    plugins.load_plugin_catalog(f"file://{path}")

    assert calls == [(path.read_bytes(), "sig")]
    assert "demo" in plugins.PLUGIN_CATALOG


def test_load_catalog_bad_signature(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    import genecoder.plugin_manager as plugins

    catalog = {"plugins": {"demo": {"description": "Demo"}}, "signature": "sig"}
    path = tmp_path / "cat.json"
    path.write_text(json.dumps(catalog))

    monkeypatch.setattr(plugins, "_verify_catalog_signature", lambda d, s: False)
    plugins.PLUGIN_CATALOG.clear()
    with caplog.at_level(logging.WARNING):
        plugins.load_plugin_catalog(f"file://{path}")

    assert "Invalid catalog signature" in caplog.text
    assert not plugins.PLUGIN_CATALOG
