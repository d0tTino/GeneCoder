import pytest

pytest.importorskip("fastapi_limiter")

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

import web.main as main

main.API_TOKEN = "test-token"
client = TestClient(main.app)

AUTH_HEADERS = {"Authorization": f"Bearer {main.API_TOKEN}"}


def test_analyze_endpoint() -> None:
    fasta = ">seq\nATGC\n"
    r = client.post("/analyze", json={"fasta_data": fasta})
    assert r.status_code == 200
    data = r.json()
    assert data["length"] == 4
    assert abs(data["gc_content"] - 0.5) < 1e-6
    assert data["max_homopolymer"] == 1


def test_report_endpoint() -> None:
    enc = {
        "fasta": ">seq\nACGT\n",
        "encoded_dna": "ACGT",
        "metrics": {"gc": 0.5},
        "info_messages": [],
    }
    r = client.post("/report", json={"data": enc, "type": "encode", "format": "html"})
    assert r.status_code == 200
    assert "<h1>Encoding Report</h1>" in r.json()["report"]


def test_dashboard_metrics_requires_token() -> None:
    payload = {"dna_sequence": "ACGT"}
    r = client.post("/dashboard/metrics", json=payload)
    assert r.status_code == 401


def test_dashboard_metrics_with_token() -> None:
    payload = {"dna_sequence": "ACGT"}
    r = client.post("/dashboard/metrics", headers=AUTH_HEADERS, json=payload)
    assert r.status_code == 200
    data = r.json()
    assert set(data) >= {"gc_content", "max_homopolymer", "error_rate", "plot"}


def test_report_invalid_request() -> None:
    r = client.post("/report", json={"data": "bad", "type": "encode"})
    assert r.status_code == 422
