import base64
import pytest

pytest.importorskip("fastapi_limiter")
fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("deepdna")
from fastapi.testclient import TestClient

import web.main as main
from genecoder.deepdna_codec import encode_data_deepdna

main.API_TOKEN = "test-token"
client = TestClient(main.app)

AUTH_HEADERS = {"Authorization": f"Bearer {main.API_TOKEN}"}


def test_deepdna_endpoint() -> None:
    data = b"deepdna endpoint"
    encoded, info = encode_data_deepdna(data)
    payload = {
        "encoded": base64.b64encode(encoded).decode(),
        "info": info,
    }
    r = client.post("/dashboard/deepdna", headers=AUTH_HEADERS, json=payload)
    assert r.status_code == 200
    decoded = base64.b64decode(r.json()["decoded_bytes"])
    assert decoded == data

