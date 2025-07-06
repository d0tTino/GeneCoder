import base64
import hashlib
import json
import pytest

pytest.importorskip("fastapi_limiter")

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

import web.main as main

client = TestClient(main.app)


from pathlib import Path
from fastapi import Request


def test_chunk_upload_and_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GENECODER_TMP", str(tmp_path))
    main.FastAPILimiter.redis = None  # type: ignore[attr-defined]
    data = b"chunk data"
    payload = {
        "file_id": "file1",
        "offset": 1,
        "data": base64.b64encode(data).decode(),
    }
    r = client.post("/upload-chunk", json=payload)
    assert r.status_code == 200
    expected_hash = hashlib.sha256(data).hexdigest()
    assert r.json()["hash"] == expected_hash
    chunk_dir = tmp_path / "chunks" / "file1"
    chunk_path = chunk_dir / "1.chunk"
    assert chunk_path.is_file()
    assert chunk_path.read_bytes() == data
    manifest_path = chunk_dir / "upload.manifest"
    assert manifest_path.is_file()
    manifest = manifest_path.read_text().splitlines()
    assert manifest == [json.dumps({"offset": 1, "hash": expected_hash})]

    r2 = client.get("/download-chunk", params={"file_id": "file1", "offset": 1})
    assert r2.status_code == 200
    assert base64.b64decode(r2.json()["data"]) == data


def test_rate_limiter_requires_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GENECODER_TMP", str(tmp_path))
    main.FastAPILimiter.redis = object()  # type: ignore[attr-defined]

    async def fake_rate_limit(request: Request, _response: object) -> None:
        if "authorization" not in request.headers:
            raise main.HTTPException(status_code=401, detail="missing token")  # type: ignore[attr-defined]

    monkeypatch.setattr(main, "rate_limit", fake_rate_limit)

    payload = {
        "file_id": "file2",
        "offset": 0,
        "data": base64.b64encode(b"data").decode(),
    }
    r = client.post("/upload-chunk", json=payload)
    assert r.status_code == 401

    r2 = client.post(
        "/upload-chunk",
        json=payload,
        headers={"Authorization": "Bearer t"},
    )
    assert r2.status_code == 200



def test_upload_chunk_missing_field(tmp_path, monkeypatch):
    monkeypatch.setenv("GENECODER_TMP", str(tmp_path))
    main.FastAPILimiter.redis = None
    payload = {"offset": 0, "data": base64.b64encode(b"d").decode()}
    r = client.post("/upload-chunk", json=payload)
    assert r.status_code == 422


def test_download_chunk_not_found(monkeypatch, tmp_path):
    monkeypatch.setenv("GENECODER_TMP", str(tmp_path))
    main.FastAPILimiter.redis = None
    r = client.get("/download-chunk", params={"file_id": "missing", "offset": 1})
    assert r.status_code == 404


@pytest.mark.parametrize(
    "bad_id",
    [
        "../bad",
        "foo/../bar",
        "..",
        "foo/bar",
        "..%2fetc",
        "..%2f..%2fsecret",
        "..\\evil",
        "..%5c..%5cwin",
    ],
)
def test_invalid_file_ids_rejected_upload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bad_id: str) -> None:
    monkeypatch.setenv("GENECODER_TMP", str(tmp_path))
    main.FastAPILimiter.redis = None
    payload = {
        "file_id": bad_id,
        "offset": 0,
        "data": base64.b64encode(b"x").decode(),
    }
    r = client.post("/upload-chunk", json=payload)
    assert r.status_code == 400


@pytest.mark.parametrize(
    "bad_id",
    [
        "../bad",
        "foo/../bar",
        "..",
        "foo/bar",
        "..%2fetc",
        "..%2f..%2fsecret",
        "..\\evil",
        "..%5c..%5cwin",
    ],
)
def test_invalid_file_ids_rejected_download(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bad_id: str) -> None:
    monkeypatch.setenv("GENECODER_TMP", str(tmp_path))
    main.FastAPILimiter.redis = None
    r = client.get("/download-chunk", params={"file_id": bad_id, "offset": 0})
    assert r.status_code == 400
