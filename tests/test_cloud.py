import argparse
import json
from pathlib import Path
from typing import cast

import httpx
import pytest

from genecoder.cloud import CloudClient
from genecoder.cli import cloud as cloud_cli


def test_cloud_client_submit() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["data"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"job_id": "jid"})

    transport = httpx.MockTransport(handler)
    client = CloudClient(
        "http://s",
        client=httpx.Client(base_url="http://s", transport=transport),
    )
    jid = client.submit("bundle", {"a": 1})
    assert jid == "jid"
    assert captured["path"] == "/jobs"
    assert captured["data"] == {"type": "bundle", "payload": {"a": 1}}


def test_cloud_client_submit_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    client = CloudClient(
        "http://s",
        client=httpx.Client(base_url="http://s", transport=transport),
    )
    with pytest.raises(RuntimeError, match="Failed to submit job"):
        client.submit("bundle", {"a": 1})


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
    args = argparse.Namespace(bundle=str(bundle), server="http://s", token=None)
    cloud_cli._handle_submit(args)
    assert calls["job_type"] == "bundle"
    assert "archive" in cast(dict[str, object], calls["payload"])
    assert calls["base_url"] == "http://s"
    assert calls["token"] is None
