import base64
import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from web.main import app

client = TestClient(app)


def test_encode_decode_roundtrip() -> None:
    payload = base64.b64encode(b"web api").decode()
    r = client.post("/encode", json={"data": payload, "options": {"method": "Base-4 Direct"}})
    assert r.status_code == 200
    fasta = r.json()["fasta"]
    r2 = client.post("/decode", json={"fasta_data": fasta})
    assert r2.status_code == 200
    decoded = base64.b64decode(r2.json()["decoded_bytes"])
    assert decoded == b"web api"
