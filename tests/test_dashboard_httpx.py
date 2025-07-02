import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from httpx import AsyncClient

import web.main as main

main.API_TOKEN = "test-token"

@pytest.mark.asyncio
async def test_dashboard_metrics_async() -> None:
    async with AsyncClient(app=main.app, base_url="http://test") as ac:
        resp = await ac.post(
            "/dashboard/metrics",
            headers={"Authorization": f"Bearer {main.API_TOKEN}"},
            json={"dna_sequence": "ACGT"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert set(data) >= {"gc_content", "max_homopolymer", "error_rate", "plot"}
    assert isinstance(data["gc_content"], float)
    assert isinstance(data["max_homopolymer"], int)
    assert isinstance(data["error_rate"], float)
    assert isinstance(data["plot"], str)
