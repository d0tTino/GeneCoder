import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from genecoder import dashboard
from genecoder.flet_handlers import compare_run_artifacts, load_run_artifact
import web.main as web_main


web_main.API_TOKEN = "test-token"
AUTH_HEADERS = {"Authorization": f"Bearer {web_main.API_TOKEN}"}


def _run_fixture(run_id: str, ber: float) -> dict[str, object]:
    return {
        "schema_version": "1.2",
        "run_id": run_id,
        "profiles": {"encoding": "reverse", "simulation": "none", "decode": "reverse"},
        "seeds": {"global": 1, "encode": 1, "simulate": 1, "decode": 1, "provenance": {}},
        "runtime": {"total_seconds": 1.0, "encode_seconds": 0.1, "simulate_seconds": 0.1, "decode_seconds": 0.1},
        "stages": {
            "encode": {"metrics": {"gc_content": 0.5, "gc_variance": 0.01, "max_homopolymer": 2}},
            "simulate": {"metrics": {"substitutions": 1, "insertions": 0, "deletions": 0, "coverage": 5}},
            "decode": {"metrics": {"decode_success": True, "decode_success_rate": 1.0, "ecc_success_rates": {}}},
        },
        "outcome": {"ber": ber, "throughput": 10.0, "dropout_rate": 0.0, "gc_stress": 0.01, "homopolymer_stress": 2, "metrics": {}},
        "constraint_outcomes": {"summary": None, "by_oligo": {}},
        "decode_outcomes": {"decode_success": True, "decode_success_rate": 1.0, "ecc_success_rates": {}},
        "provenance": {"source_format": "test", "generator": "tests"},
    }


def test_artifact_load_parity_flet_streamlit_api(tmp_path: Path) -> None:
    client = TestClient(web_main.app)
    run_path = tmp_path / "run.metrics.json"
    run_path.write_text(json.dumps(_run_fixture("run-1", 0.01)), encoding="utf-8")

    flet_loaded = load_run_artifact(str(run_path))
    streamlit_metrics = dashboard._load_metrics(str(run_path))

    response = client.post(
        "/artifacts/load",
        headers=AUTH_HEADERS,
        params={"artifact_path": str(run_path)},
    )
    assert response.status_code == 200
    api_loaded = response.json()

    assert flet_loaded["run_id"] == api_loaded["run_id"]
    assert flet_loaded["dashboard_metrics"] == api_loaded["dashboard_metrics"]
    assert streamlit_metrics == api_loaded["dashboard_metrics"]


def test_compare_parity_flet_and_api(tmp_path: Path) -> None:
    client = TestClient(web_main.app)
    baseline = tmp_path / "base.json"
    candidate = tmp_path / "cand.json"
    baseline.write_text(json.dumps(_run_fixture("base", 0.01)), encoding="utf-8")
    candidate.write_text(json.dumps(_run_fixture("cand", 0.03)), encoding="utf-8")

    flet_cmp = compare_run_artifacts(str(baseline), str(candidate))

    response = client.post(
        "/runs/compare",
        headers=AUTH_HEADERS,
        json={"baseline": str(baseline), "candidates": [str(candidate)]},
    )
    assert response.status_code == 200
    api_cmp = response.json()

    assert flet_cmp == api_cmp
