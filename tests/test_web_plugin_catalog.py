import asyncio
from pathlib import Path

import pytest

httpx = pytest.importorskip("httpx")
fastapi = pytest.importorskip("fastapi")

import web.main as main


# helper function to make requests against the FastAPI app

def _request(method: str, url: str, **kwargs: object) -> httpx.Response:
    async def _call() -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            return await ac.request(method, url, **kwargs)

    return asyncio.run(_call())


def test_plugins_endpoint_returns_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GENECODER_API_TOKEN", "tok")
    catalog_file = tmp_path / "catalog_data.json"
    challenge_file = tmp_path / "challenge_data.json"

    monkeypatch.setattr(main.plugin_catalog, "CATALOG_PATH", catalog_file)
    monkeypatch.setattr(main.plugin_catalog, "CHALLENGE_PATH", challenge_file)
    main.plugin_catalog._plugins = None
    main.plugin_catalog._challenge = None

    r = _request("GET", "/catalog/plugins")
    assert r.status_code == 200
    assert r.json() == {"plugins": []}


def test_challenge_roundtrip_requires_auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GENECODER_API_TOKEN", "tok")
    main.plugin_catalog.API_TOKEN = "tok"
    catalog_file = tmp_path / "catalog_data.json"
    challenge_file = tmp_path / "challenge_data.json"

    monkeypatch.setattr(main.plugin_catalog, "CATALOG_PATH", catalog_file)
    monkeypatch.setattr(main.plugin_catalog, "CHALLENGE_PATH", challenge_file)
    main.plugin_catalog._plugins = None
    main.plugin_catalog._challenge = None
    main.FastAPILimiter.redis = None  # type: ignore[attr-defined]

    # unauthorized request should fail
    r = _request("POST", "/catalog/challenge", json={"name": "alice", "points": 5})
    assert r.status_code == 401

    # authorized request adds entry
    r2 = _request(
        "POST",
        "/catalog/challenge",
        headers={"Authorization": "Bearer tok"},
        json={"name": "alice", "points": 5},
    )
    assert r2.status_code == 200

    # reset in-memory cache to ensure data is read from disk
    main.plugin_catalog._challenge = None
    r3 = _request("GET", "/catalog/challenge")
    assert r3.status_code == 200
    assert r3.json() == {"entries": {"alice": 5}}


def test_challenge_multiple_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GENECODER_API_TOKEN", "tok")
    main.plugin_catalog.API_TOKEN = "tok"
    challenge_file = tmp_path / "challenge_data.json"
    monkeypatch.setattr(main.plugin_catalog, "CHALLENGE_PATH", challenge_file)
    main.plugin_catalog._challenge = None
    main.FastAPILimiter.redis = None  # type: ignore[attr-defined]

    for name, pts in [("alice", 3), ("bob", 7)]:
        r = _request(
            "POST",
            "/catalog/challenge",
            headers={"Authorization": "Bearer tok"},
            json={"name": name, "points": pts},
        )
        assert r.status_code == 200

    main.plugin_catalog._challenge = None
    r2 = _request("GET", "/catalog/challenge")
    assert r2.status_code == 200
    assert r2.json() == {"entries": {"alice": 3, "bob": 7}}


def test_challenge_update_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GENECODER_API_TOKEN", "tok")
    main.plugin_catalog.API_TOKEN = "tok"
    challenge_file = tmp_path / "challenge_data.json"
    monkeypatch.setattr(main.plugin_catalog, "CHALLENGE_PATH", challenge_file)
    main.plugin_catalog._challenge = None
    main.FastAPILimiter.redis = None  # type: ignore[attr-defined]

    r1 = _request(
        "POST",
        "/catalog/challenge",
        headers={"Authorization": "Bearer tok"},
        json={"name": "alice", "points": 5},
    )
    assert r1.status_code == 200

    r2 = _request(
        "POST",
        "/catalog/challenge",
        headers={"Authorization": "Bearer tok"},
        json={"name": "alice", "points": 9},
    )
    assert r2.status_code == 200

    main.plugin_catalog._challenge = None
    r3 = _request("GET", "/catalog/challenge")
    assert r3.status_code == 200
    assert r3.json() == {"entries": {"alice": 9}}

