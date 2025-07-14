import asyncio
import json
import pytest

httpx = pytest.importorskip("httpx")

from genecoder.cloud import CloudClient, AsyncCloudClient


def test_cloud_client_submit_success() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["data"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"job_id": "jid"})

    transport = httpx.MockTransport(handler)
    client = CloudClient("https://server", client=httpx.Client(base_url="https://server", transport=transport))
    jid = client.submit("bundle", {"a": 1})
    assert jid == "jid"
    assert captured["path"] == "/jobs"
    assert captured["data"] == {"type": "bundle", "payload": {"a": 1}}


def test_cloud_client_get_job() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.path == "/jobs/jid"
            return httpx.Response(200, json={"status": "completed"})
        return httpx.Response(200, json={"job_id": "jid"})

    transport = httpx.MockTransport(handler)
    client = CloudClient("https://server", client=httpx.Client(base_url="https://server", transport=transport))
    jid = client.submit("bundle", {})
    assert client.get_job(jid)["status"] == "completed"


def test_cloud_client_submit_failure() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    client = CloudClient("https://server", client=httpx.Client(base_url="https://server", transport=transport))
    with pytest.raises(RuntimeError, match="Failed to submit job"):
        client.submit("bundle", {})


def test_async_cloud_client_submit_success() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["data"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"job_id": "jid"})

    transport = httpx.MockTransport(handler)

    async def _run() -> None:
        client = AsyncCloudClient(
            "https://server",
            client=httpx.AsyncClient(base_url="https://server", transport=transport),
        )
        jid = await client.submit("bundle", {"a": 1})
        assert jid == "jid"
        assert captured["path"] == "/jobs"
        assert captured["data"] == {"type": "bundle", "payload": {"a": 1}}
        await client.close()

    asyncio.run(_run())


def test_async_cloud_client_get_job() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.path == "/jobs/jid"
            return httpx.Response(200, json={"status": "completed"})
        return httpx.Response(200, json={"job_id": "jid"})

    transport = httpx.MockTransport(handler)

    async def _run() -> None:
        client = AsyncCloudClient(
            "https://server",
            client=httpx.AsyncClient(base_url="https://server", transport=transport),
        )
        jid = await client.submit("bundle", {})
        status = await client.get_job(jid)
        assert status["status"] == "completed"
        await client.close()

    asyncio.run(_run())


def test_async_cloud_client_submit_failure() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)

    async def _run() -> None:
        client = AsyncCloudClient(
            "https://server",
            client=httpx.AsyncClient(base_url="https://server", transport=transport),
        )
        with pytest.raises(RuntimeError, match="Failed to submit job"):
            await client.submit("bundle", {})
        await client.close()

    asyncio.run(_run())
