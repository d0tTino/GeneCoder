import pytest

pytest.importorskip("fastapi_limiter")
fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from genecoder.utils import get_max_homopolymer_length
import web.main as main

client = TestClient(main.app)


def test_design_validate_valid_sequence() -> None:
    payload = {"sequence": "ACGTACGT"}
    r = client.post("/design/validate", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is True
    assert abs(data["gc_content"] - 0.5) < 1e-6
    assert data["max_homopolymer"] <= 4


def test_design_validate_invalid_gc() -> None:
    payload = {"sequence": "GGGGG", "gc_min": 0.0, "gc_max": 0.4}
    r = client.post("/design/validate", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is False
    assert data["gc_content"] > 0.4


def test_design_validate_homopolymer() -> None:
    payload = {"sequence": "AAAA", "gc_min": 0.0, "gc_max": 1.0, "max_homopolymer": 2}
    r = client.post("/design/validate", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is False
    assert data["max_homopolymer"] > 2


def test_design_validate_gc_boundary() -> None:
    payload = {"sequence": "GGGG", "gc_min": 1.0, "gc_max": 1.0}
    r = client.post("/design/validate", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is True
    assert data["gc_content"] == 1.0


def test_design_fix_basic() -> None:
    payload = {"sequence": "AAAA", "max_homopolymer": 1}
    r = client.post("/design/fix", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert get_max_homopolymer_length(data["sequence"]) <= 1
    assert 0.25 <= data["gc_content"] <= 0.75


def test_design_fix_gc_extreme() -> None:
    payload = {"sequence": "AAAA", "gc_min": 1.0, "gc_max": 1.0, "max_homopolymer": 3}
    r = client.post("/design/fix", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["gc_content"] >= 0.75
    assert get_max_homopolymer_length(data["sequence"]) <= 3
