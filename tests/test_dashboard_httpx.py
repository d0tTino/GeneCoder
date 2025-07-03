import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import web.main as main

main.API_TOKEN = "test-token"


def _client() -> TestClient:
    return TestClient(main.app)


def test_dashboard_page() -> None:
    with _client() as client:
        resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "GeneCoder Dashboard" in resp.text


def test_dashboard_metrics() -> None:
    with _client() as client:
        resp = client.post(
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


def test_dashboard_metrics_invalid_length() -> None:
    with _client() as client:
        resp = client.post(
            "/dashboard/metrics",
            headers={"Authorization": f"Bearer {main.API_TOKEN}"},
            json={"dna_sequence": "AAA"},
        )
    assert resp.status_code == 400
    assert "multiple of 4" in resp.json()["detail"]


def test_dashboard_plot_data_invalid_chars() -> None:
    with _client() as client:
        resp = client.post(
            "/dashboard/plot-data",
            headers={"Authorization": f"Bearer {main.API_TOKEN}"},
            json={"dna_sequence": "ACGTX"},
        )
    assert resp.status_code == 400
    assert "Invalid" in resp.json()["detail"]
