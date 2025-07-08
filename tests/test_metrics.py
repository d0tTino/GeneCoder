import json
from pathlib import Path

import pytest
from tests.test_cli import run_cli_command

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


def test_encode_increments_metrics(tmp_path: Path, monkeypatch) -> None:
    metrics_path = tmp_path / "m.json"
    monkeypatch.setenv("GENECODER_METRICS_PATH", str(metrics_path))
    inp = tmp_path / "f.txt"
    inp.write_text("x")
    res = run_cli_command(["encode", "--input-files", str(inp), "--output-dir", str(tmp_path)])
    assert res.returncode == 0, res.stderr
    data = json.loads(metrics_path.read_text())
    assert data["encode_runs"] == 1


def test_stats_cli(tmp_path: Path, monkeypatch) -> None:
    metrics_path = tmp_path / "s.json"
    metrics_path.write_text(json.dumps({"encode_runs": 2, "bundle_runs": 1}))
    monkeypatch.setenv("GENECODER_METRICS_PATH", str(metrics_path))
    res = run_cli_command(["stats"])
    assert res.returncode == 0
    out = res.stdout.strip().splitlines()
    assert "encode_runs: 2" in out
    assert "bundle_runs: 1" in out


def test_metrics_endpoint(tmp_path: Path, monkeypatch) -> None:
    metrics_path = tmp_path / "web.json"
    metrics_path.write_text(json.dumps({"bundle_runs": 5}))
    monkeypatch.setenv("GENECODER_METRICS_PATH", str(metrics_path))
    import importlib
    main = importlib.import_module("web.main")
    importlib.reload(main)
    main.API_TOKEN = "test-token"
    client = TestClient(main.app)
    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.json()["bundle_runs"] == 5
