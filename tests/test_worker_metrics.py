import base64
import tempfile
import zipfile
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from genecoder.cloud import worker


def _build_archive(bundle_path: Path) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        archive = Path(tmpdir) / "bundle.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.write(bundle_path, arcname=bundle_path.name)
        return base64.b64encode(archive.read_bytes()).decode()


def _build_archive_no_yaml(tmp_path: Path) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        archive = Path(tmpdir) / "bundle.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("file.txt", "x")
        return base64.b64encode(archive.read_bytes()).decode()


def test_worker_metrics_updated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    metrics_path = tmp_path / "metrics.json"
    monkeypatch.setenv("GENECODER_METRICS_PATH", str(metrics_path))
    worker.API_TOKEN = "tok"
    called: dict[str, str] = {}

    def dummy(args):
        called["config"] = Path(args.config).name
        from genecoder.metrics import increment
        increment("bundle_runs")

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
    assert called["config"] == "b.yaml"
    from genecoder import metrics

    assert metrics.get_metrics().get("bundle_runs") == 1


def test_worker_missing_yaml(tmp_path: Path) -> None:
    worker.API_TOKEN = "tok"
    archive_b64 = _build_archive_no_yaml(tmp_path)
    client = TestClient(worker.app)
    r = client.post(
        "/jobs",
        headers={"Authorization": "Bearer tok"},
        json={"type": "bundle", "payload": {"archive": archive_b64}},
    )
    assert r.status_code == 400
    assert "Bundle file not found" in r.json()["detail"]

