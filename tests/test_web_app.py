import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient
from genecoder.utils import get_max_homopolymer_length

import base64

import web.main as main

main.API_TOKEN = "test-token"
app = main.app
index_path = main.index_path
helix_index_path = main.helix_index_path
design_index_path = main.design_index_path
client = TestClient(app)

AUTH_HEADERS = {"Authorization": f"Bearer {main.API_TOKEN}"}


def test_root_route_serves_index_html() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "GeneCoder Web" in response.text


def test_static_index_served() -> None:
    response = client.get("/static/index.html")
    assert response.status_code == 200
    assert response.text == index_path.read_text(encoding="utf-8")


def test_helix_route_serves_ui() -> None:
    response = client.get("/helix")
    assert response.status_code == 200
    assert response.text == helix_index_path.read_text(encoding="utf-8")


def test_helix_ui_static() -> None:
    response = client.get("/helix-ui/index.html")
    assert response.status_code == 200
    assert response.text == helix_index_path.read_text(encoding="utf-8")


def test_dashboard_route() -> None:
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text


def test_encode_endpoint() -> None:
    payload = base64.b64encode(b"web app").decode()
    r = client.post(
        "/encode",
        headers=AUTH_HEADERS,
        json={"data": payload, "options": {"method": "Base-4 Direct"}},
    )
    assert r.status_code == 200
    data = r.json()
    assert set(data) >= {"fasta", "encoded_dna", "metrics", "info_messages"}


def test_decode_endpoint() -> None:
    payload = base64.b64encode(b"roundtrip").decode()
    r = client.post(
        "/encode",
        headers=AUTH_HEADERS,
        json={"data": payload, "options": {"method": "Base-4 Direct"}},
    )
    fasta = r.json()["fasta"]
    r2 = client.post("/decode", headers=AUTH_HEADERS, json={"fasta_data": fasta})
    assert r2.status_code == 200
    decoded = base64.b64decode(r2.json()["decoded_bytes"])
    assert decoded == b"roundtrip"


def test_analyze_endpoint_valid() -> None:
    fasta = ">seq\nATGC\n"
    r = client.post("/analyze", json={"fasta_data": fasta})
    assert r.status_code == 200
    data = r.json()
    assert data["length"] == 4
    assert abs(data["gc_content"] - 0.5) < 1e-6


def test_analyze_endpoint_invalid_fasta() -> None:
    r = client.post("/analyze", json={"fasta_data": "invalid"})
    assert r.status_code == 400


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


def test_design_page() -> None:
    response = client.get("/design")
    assert response.status_code == 200
    assert response.text == design_index_path.read_text(encoding="utf-8")


def test_design_validate_endpoint() -> None:
    payload = {"sequence": "ACGT"}
    r = client.post("/design/validate", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert set(data) >= {"valid", "gc_content", "max_homopolymer"}


def test_design_fix_endpoint() -> None:
    payload = {"sequence": "AAAA", "max_homopolymer": 2}
    r = client.post("/design/fix", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "sequence" in data
    assert get_max_homopolymer_length(data["sequence"]) <= 2
