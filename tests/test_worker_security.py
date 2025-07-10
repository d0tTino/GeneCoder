import base64
import zipfile
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from genecoder.cloud import worker


def _build_archive(name: str, tmp_path: Path) -> str:
    archive = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(name, "x")
    return base64.b64encode(archive.read_bytes()).decode()


@pytest.mark.parametrize("name", ["../evil.yaml", "/abs.yaml"])
def test_worker_rejects_bad_paths(tmp_path: Path, name: str) -> None:
    worker.API_TOKEN = "tok"
    client = TestClient(worker.app)
    archive_b64 = _build_archive(name, tmp_path)
    r = client.post(
        "/jobs",
        headers={"Authorization": "Bearer tok"},
        json={"type": "bundle", "payload": {"archive": archive_b64}},
    )
    assert r.status_code == 400
