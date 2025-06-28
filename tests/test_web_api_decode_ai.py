import base64
import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("dnaformer")
from fastapi.testclient import TestClient

from web.main import app
from genecoder.dnaformer_codec import encode_data_dnaformer

client = TestClient(app)


def test_decode_ai_endpoint() -> None:
    data = b"ai endpoint"
    encoded, info = encode_data_dnaformer(data)
    payload = {
        "encoded": base64.b64encode(encoded).decode(),
        "info": info,
    }
    r = client.post("/decode/ai", json=payload)
    assert r.status_code == 200
    decoded = base64.b64decode(r.json()["decoded_bytes"])
    assert decoded == data
