import base64
import zipfile
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from genecoder.compat.legacy.cloud import worker


def _build_archive(name: str, tmp_path: Path) -> str:
    archive = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(name, "x")
    return base64.b64encode(archive.read_bytes()).decode()


def _build_symlink_archive(tmp_path: Path) -> str:
    archive = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zi = zipfile.ZipInfo("link")
        zi.create_system = 3
        zi.external_attr = 0o120777 << 16
        zf.writestr(zi, "target")
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


def test_worker_rejects_symlink(tmp_path: Path) -> None:
    worker.API_TOKEN = "tok"
    client = TestClient(worker.app)
    archive_b64 = _build_symlink_archive(tmp_path)
    r = client.post(
        "/jobs",
        headers={"Authorization": "Bearer tok"},
        json={"type": "bundle", "payload": {"archive": archive_b64}},
    )
    assert r.status_code == 400
