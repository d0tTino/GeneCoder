import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from web.main import app

client = TestClient(app)


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
