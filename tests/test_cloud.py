import argparse
import json
import tempfile
from pathlib import Path
from typing import cast

import pytest
httpx = pytest.importorskip("httpx")
import asyncio

from genecoder.cloud import CloudClient, AsyncCloudClient
from genecoder.cli import cloud as cloud_cli


def test_cloud_client_submit() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["data"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"job_id": "jid"})

    transport = httpx.MockTransport(handler)
    client = CloudClient(
        "https://s",
        client=httpx.Client(base_url="https://s", transport=transport),
    )
    jid = client.submit("bundle", {"a": 1})
    assert jid == "jid"
    assert captured["path"] == "/jobs"
    assert captured["data"] == {"type": "bundle", "payload": {"a": 1}}


def test_async_cloud_client_submit() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["data"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"job_id": "jid"})

    transport = httpx.MockTransport(handler)

    async def _run() -> None:
        client = AsyncCloudClient(
            "https://s",
            client=httpx.AsyncClient(base_url="https://s", transport=transport),
        )
        jid = await client.submit("bundle", {"a": 1})
        assert jid == "jid"
        assert captured["path"] == "/jobs"
        assert captured["data"] == {"type": "bundle", "payload": {"a": 1}}
        await client.close()

    asyncio.run(_run())


def test_cloud_client_submit_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    client = CloudClient(
        "https://s",
        client=httpx.Client(base_url="https://s", transport=transport),
    )
    with pytest.raises(RuntimeError, match="Failed to submit job"):
        client.submit("bundle", {"a": 1})


def test_cloud_client_invalid_token() -> None:
    """Submitting with an invalid token raises an error."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Bearer bad"
        return httpx.Response(401)

    transport = httpx.MockTransport(handler)
    client = CloudClient(
        "https://s",
        token="bad",
        client=httpx.Client(base_url="https://s", transport=transport),
    )
    with pytest.raises(RuntimeError, match="Failed to submit job"):
        client.submit("bundle", {"a": 1})


def test_async_cloud_client_invalid_token() -> None:
    """Async client handles invalid tokens."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Bearer bad"
        return httpx.Response(401)

    transport = httpx.MockTransport(handler)

    async def _run() -> None:
        client = AsyncCloudClient(
            "https://s",
            token="bad",
            client=httpx.AsyncClient(base_url="https://s", transport=transport),
        )
        with pytest.raises(RuntimeError, match="Failed to submit job"):
            await client.submit("bundle", {"a": 1})
        await client.close()

    asyncio.run(_run())


def test_cloud_client_bad_payload() -> None:
    """Invalid JSON responses raise ``ValueError``."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"foo": "bar"})

    transport = httpx.MockTransport(handler)
    client = CloudClient(
        "https://s",
        client=httpx.Client(base_url="https://s", transport=transport),
    )
    with pytest.raises(ValueError, match="Invalid response from server"):
        client.submit("bundle", {"a": 1})


def test_async_cloud_client_bad_payload() -> None:
    """Async client errors on invalid JSON responses."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"foo": "bar"})

    transport = httpx.MockTransport(handler)

    async def _run() -> None:
        client = AsyncCloudClient(
            "https://s",
            client=httpx.AsyncClient(base_url="https://s", transport=transport),
        )
        with pytest.raises(ValueError, match="Invalid response from server"):
            await client.submit("bundle", {"a": 1})
        await client.close()

    asyncio.run(_run())


def test_cloud_submit_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = tmp_path / "b.yaml"
    bundle.write_text("encode:\n  input_files: []\n")

    calls: dict[str, object] = {}

    class DummyClient:
        def __init__(self, base_url: str, token: str | None = None, client: object | None = None) -> None:
            calls["base_url"] = base_url
            calls["token"] = token

        def submit(self, job_type: str, payload: dict[str, object]) -> str:
            calls["job_type"] = job_type
            calls["payload"] = payload
            return "jid"

        def close(self) -> None:
            pass

        def __enter__(self) -> "DummyClient":
            return self

        def __exit__(self, exc_type: BaseException | None, exc: BaseException | None, tb: object | None) -> None:
            pass

    monkeypatch.setattr("genecoder.cloud.CloudClient", DummyClient)
    args = argparse.Namespace(bundle=str(bundle), server="https://s", token=None)
    cloud_cli._handle_submit(args)
    assert calls["job_type"] == "bundle"
    assert "archive" in cast(dict[str, object], calls["payload"])
    assert calls["base_url"] == "https://s"
    assert calls["token"] is None


def test_async_cloud_submit_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = tmp_path / "b.yaml"
    bundle.write_text("encode:\n  input_files: []\n")

    calls: dict[str, object] = {}

    class DummyAsyncClient:
        def __init__(self, base_url: str, token: str | None = None, client: object | None = None) -> None:
            calls["base_url"] = base_url
            calls["token"] = token

        async def submit(self, job_type: str, payload: dict[str, object]) -> str:
            calls["job_type"] = job_type
            calls["payload"] = payload
            return "jid"

        async def close(self) -> None:
            pass

        async def __aenter__(self) -> "DummyAsyncClient":
            return self

        async def __aexit__(self, exc_type: BaseException | None, exc: BaseException | None, tb: object | None) -> None:
            pass

    monkeypatch.setattr("genecoder.cloud.AsyncCloudClient", DummyAsyncClient)
    args = argparse.Namespace(bundle=str(bundle), server="https://s", token=None, use_async=True)
    cloud_cli._handle_submit(args)
    assert calls["job_type"] == "bundle"
    assert "archive" in cast(dict[str, object], calls["payload"])
    assert calls["base_url"] == "https://s"
    assert calls["token"] is None

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from genecoder.cloud import worker


def _build_archive(bundle_path: Path) -> str:
    import base64
    import zipfile

    with tempfile.TemporaryDirectory() as tmpdir:
        archive = Path(tmpdir) / "bundle.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.write(bundle_path, arcname=bundle_path.name)
        return base64.b64encode(archive.read_bytes()).decode()


def test_worker_integration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    worker.API_TOKEN = "tok"
    called: dict[str, object] = {}

    def dummy(args: argparse.Namespace) -> None:
        called["config"] = args.config

    monkeypatch.setattr(worker.bundle_cli, "_handle_run", dummy)
    bundle_file = tmp_path / "b.yaml"
    bundle_file.write_text("encode:\n  input_files: []\n")
    archive_b64 = _build_archive(bundle_file)

    def handler(request: httpx.Request) -> httpx.Response:
        transport = httpx.ASGITransport(app=worker.app)

        async def _call() -> httpx.Response:
            async with httpx.AsyncClient(transport=transport, base_url="http://worker") as ac:
                resp = await ac.request(
                    request.method,
                    request.url.path,
                    headers=request.headers,
                    content=request.content,
                )
            return resp

        resp = asyncio.run(_call())
        return httpx.Response(
            resp.status_code, headers=resp.headers, content=resp.content
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="http://worker")
    client = CloudClient("http://worker", token="tok", client=http_client)
    jid = client.submit("bundle", {"archive": archive_b64})
    http_client.close()
    assert jid
    assert Path(called["config"]).name == "b.yaml"


def test_worker_integration_async(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    worker.API_TOKEN = "tok"
    called: dict[str, object] = {}

    def dummy(args: argparse.Namespace) -> None:
        called["config"] = args.config

    monkeypatch.setattr(worker.bundle_cli, "_handle_run", dummy)
    bundle_file = tmp_path / "b.yaml"
    bundle_file.write_text("encode:\n  input_files: []\n")
    archive_b64 = _build_archive(bundle_file)

    async def _run() -> None:
        transport = httpx.ASGITransport(app=worker.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://worker") as ac_client:
            async with AsyncCloudClient("http://worker", token="tok", client=ac_client) as ac:
                jid = await ac.submit("bundle", {"archive": archive_b64})
                assert jid
        assert Path(called["config"]).name == "b.yaml"

    asyncio.run(_run())


def test_worker_submit_requires_token(tmp_path: Path) -> None:
    """Job submissions without a token are rejected."""

    worker.API_TOKEN = "tok"
    client = TestClient(worker.app)
    bundle_file = tmp_path / "b.yaml"
    bundle_file.write_text("encode:\n  input_files: []\n")
    archive_b64 = _build_archive(bundle_file)
    r = client.post("/jobs", json={"type": "bundle", "payload": {"archive": archive_b64}})
    assert r.status_code == 401


def test_worker_submit_invalid_token(tmp_path: Path) -> None:
    """Job submissions with a bad token are rejected."""

    worker.API_TOKEN = "tok"
    client = TestClient(worker.app)
    bundle_file = tmp_path / "b.yaml"
    bundle_file.write_text("encode:\n  input_files: []\n")
    archive_b64 = _build_archive(bundle_file)
    r = client.post(
        "/jobs",
        headers={"Authorization": "Bearer bad"},
        json={"type": "bundle", "payload": {"archive": archive_b64}},
    )
    assert r.status_code == 401


def test_worker_submit_invalid_type() -> None:
    """Unsupported job types return 400."""

    worker.API_TOKEN = "tok"
    client = TestClient(worker.app)
    r = client.post(
        "/jobs",
        headers={"Authorization": "Bearer tok"},
        json={"type": "bogus", "payload": {}},
    )
    assert r.status_code == 400


def test_worker_submit_missing_archive() -> None:
    """Missing archive field returns 400."""

    worker.API_TOKEN = "tok"
    client = TestClient(worker.app)
    r = client.post(
        "/jobs",
        headers={"Authorization": "Bearer tok"},
        json={"type": "bundle", "payload": {}},
    )
    assert r.status_code == 400


def test_worker_submit_invalid_archive() -> None:
    """Invalid archive data returns 400."""

    worker.API_TOKEN = "tok"
    client = TestClient(worker.app)
    r = client.post(
        "/jobs",
        headers={"Authorization": "Bearer tok"},
        json={"type": "bundle", "payload": {"archive": "foo"}},
    )
    assert r.status_code == 400


def test_worker_submit_job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Valid job submissions invoke the bundle handler."""

    worker.API_TOKEN = "tok"
    called: dict[str, object] = {}

    def dummy(args: argparse.Namespace) -> None:
        called["config"] = args.config

    monkeypatch.setattr(worker.bundle_cli, "_handle_run", dummy)
    bundle_file = tmp_path / "b.yaml"
    bundle_file.write_text("encode:\n  input_files: []\n")
    archive_b64 = _build_archive(bundle_file)
    client = TestClient(worker.app)
    r = client.post(
        "/jobs",
        headers={"Authorization": "Bearer tok"},
        json={"type": "bundle", "payload": {"archive": archive_b64}},
    )
    assert r.status_code == 200
    assert Path(called["config"]).name == "b.yaml"
    assert r.json()["job_id"]

