import base64
import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

import web.main as main

client = TestClient(main.app)


def test_chunk_endpoints_without_redis(tmp_path):
    main.FastAPILimiter.redis = None
    data = b"no redis"
    payload = {
        "file_id": "file",
        "offset": 0,
        "data": base64.b64encode(data).decode(),
    }
    r = client.post("/upload-chunk", json=payload)
    assert r.status_code == 200
    r2 = client.get("/download-chunk", params={"file_id": "file", "offset": 0})
    assert r2.status_code == 200
    assert base64.b64decode(r2.json()["data"]) == data
