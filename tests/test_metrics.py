import json
import os
from pathlib import Path

import pytest
from tests.test_cli import run_cli_command

pytest.importorskip("fastapi")
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
    metrics_path.write_text(
        json.dumps({"encode_runs": 2, "bundle_runs": 1, "oligos_simulated": 3})
    )
    monkeypatch.setenv("GENECODER_METRICS_PATH", str(metrics_path))
    res = run_cli_command(["stats"])
    assert res.returncode == 0
    out = res.stdout.strip().splitlines()
    assert "encode_runs: 2" in out
    assert "bundle_runs: 1" in out
    assert "oligos_simulated: 3" in out


def test_metrics_endpoint(tmp_path: Path, monkeypatch) -> None:
    metrics_path = tmp_path / "web.json"
    metrics_path.write_text(
        json.dumps({"bundle_runs": 5, "oligos_simulated": 2})
    )
    monkeypatch.setenv("GENECODER_METRICS_PATH", str(metrics_path))
    import importlib
    main = importlib.import_module("web.main")
    importlib.reload(main)
    main.API_TOKEN = "test-token"
    client = TestClient(main.app)
    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.json()["bundle_runs"] == 5
    assert r.json()["oligos_simulated"] == 2


def test_pipeline_increments_metric(tmp_path: Path, monkeypatch) -> None:
    metrics_path = tmp_path / "p.json"
    monkeypatch.setenv("GENECODER_METRICS_PATH", str(metrics_path))
    from src.genecoder.channel_sim import Channel
    from src.genecoder.simulators.pipeline import ChannelPipeline

    pipeline = ChannelPipeline([Channel(0.0)])
    pipeline.simulate("ACGT")
    data = json.loads(metrics_path.read_text())
    assert data["oligos_simulated"] == 1


def test_channel_cli_increments_metric(tmp_path: Path, monkeypatch) -> None:
    metrics_path = tmp_path / "c.json"
    monkeypatch.setenv("GENECODER_METRICS_PATH", str(metrics_path))
    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"
    fasta = tmp_path / "i.fasta"
    fasta.write_text(">a\nAAAA\n>b\nTTTT\n")
    out = tmp_path / "o.fasta"
    res = run_cli_command(
        [
            "channel",
            "--input-file",
            str(fasta),
            "--output-file",
            str(out),
            "--sub-prob",
            "0.1",
            "--min-length",
            "1",
        ],
        env=env,
    )
    assert res.returncode == 0, res.stderr
    data = json.loads(metrics_path.read_text())
    assert data["oligos_simulated"] == 2
