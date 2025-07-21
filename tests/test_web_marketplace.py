import asyncio
import pytest

httpx = pytest.importorskip("httpx")
fastapi = pytest.importorskip("fastapi")

import web.main as main

main.API_TOKEN = "test-token"
AUTH_HEADERS = {"Authorization": f"Bearer {main.API_TOKEN}"}


def _request(method: str, url: str, **kwargs: object) -> httpx.Response:
    async def _call() -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            return await ac.request(method, url, **kwargs)

    return asyncio.run(_call())


def test_marketplace_page_served() -> None:
    r = _request("GET", "/marketplace")
    assert r.status_code == 200
    assert "<!DOCTYPE html>" in r.text


def test_plugin_rate_roundtrip() -> None:
    main.PLUGIN_RATINGS.clear()
    r = _request(
        "POST",
        "/plugins/rate",
        headers=AUTH_HEADERS,
        json={"name": "demo", "rating": 5},
    )
    assert r.status_code == 200
    assert r.json()["average"] == 5
    r2 = _request("GET", "/plugins/rate", headers=AUTH_HEADERS, params={"name": "demo"})
    assert r2.status_code == 200
    assert r2.json()["average"] == 5
