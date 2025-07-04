import base64
import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("dnaformer")
from fastapi.testclient import TestClient

import web.main as main
from genecoder.dnaformer_codec import encode_data_dnaformer

main.API_TOKEN = "test-token"
client = TestClient(main.app)

AUTH_HEADERS = {"Authorization": f"Bearer {main.API_TOKEN}"}


def test_decode_ai_endpoint() -> None:
    data = b"ai endpoint"
    encoded, info = encode_data_dnaformer(data)
    payload = {
        "encoded": base64.b64encode(encoded).decode(),
        "info": info,
    }
    r = client.post("/decode/ai", headers=AUTH_HEADERS, json=payload)
    assert r.status_code == 200
    decoded = base64.b64decode(r.json()["decoded_bytes"])
    assert decoded == data


def test_decode_ai_requires_token() -> None:
    data = b"no token"
    encoded, info = encode_data_dnaformer(data)
    payload = {
        "encoded": base64.b64encode(encoded).decode(),
        "info": info,
    }
    r = client.post("/decode/ai", json=payload)
    assert r.status_code == 401


def test_decode_ai_invalid_token() -> None:
    data = b"bad token"
    encoded, info = encode_data_dnaformer(data)
    payload = {
        "encoded": base64.b64encode(encoded).decode(),
        "info": info,
    }
    r = client.post(
        "/decode/ai",
        headers={"Authorization": "Bearer wrong"},
        json=payload,
    )
    assert r.status_code == 401
