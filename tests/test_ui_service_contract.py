import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

import json
from pathlib import Path

from fastapi.testclient import TestClient

from genecoder.app.ui_service import ArtifactExportRequest, UIService
import web.main as main


main.API_TOKEN = "test-token"
AUTH_HEADERS = {"Authorization": f"Bearer {main.API_TOKEN}"}


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


def test_contract_plugins_and_profiles_match_service() -> None:
    svc = UIService()
    client = TestClient(main.app)

    assert client.get("/plugins").json() == svc.list_plugins()
    assert client.get("/profiles").json() == svc.list_profiles()


def test_contract_artifact_export_load_and_compare(tmp_path: Path) -> None:
    svc = UIService()
    run_a = _run_fixture("run-a", 0.01)
    run_b = _run_fixture("run-b", 0.02)

    exported = svc.export_artifacts(
        ArtifactExportRequest(run_data=run_a, output_dir=str(tmp_path), run_id="run-a")
    )
    assert Path(exported["manifest_index"]).is_file()

    loaded = svc.load_artifact(exported["metrics_json"])
    assert loaded["run_id"] == "run-a"
    assert "dashboard_metrics" in loaded

    run_b_path = tmp_path / "run-b.metrics.json"
    run_b_path.write_text(json.dumps(run_b), encoding="utf-8")
    compared = svc.compare_artifacts(exported["metrics_json"], run_b_path)
    assert compared["baseline_run_id"] == "run-a"
    assert compared["comparisons"][0]["run_id"] == "run-b"


def test_web_contract_compare_and_export(tmp_path: Path) -> None:
    client = TestClient(main.app)
    baseline = tmp_path / "base.json"
    candidate = tmp_path / "cand.json"
    baseline.write_text(json.dumps(_run_fixture("base", 0.01)), encoding="utf-8")
    candidate.write_text(json.dumps(_run_fixture("cand", 0.03)), encoding="utf-8")

    cmp_resp = client.post(
        "/runs/compare",
        headers=AUTH_HEADERS,
        json={"baseline": str(baseline), "candidates": [str(candidate)]},
    )
    assert cmp_resp.status_code == 200
    assert cmp_resp.json()["comparisons"][0]["run_id"] == "cand"

    export_resp = client.post(
        "/artifacts/export",
        headers=AUTH_HEADERS,
        json={"run_data": _run_fixture("web", 0.01), "output_dir": str(tmp_path), "run_id": "web"},
    )
    assert export_resp.status_code == 200
    metrics_path = export_resp.json()["metrics_json"]

    load_resp = client.post(
        "/artifacts/load",
        headers=AUTH_HEADERS,
        params={"artifact_path": metrics_path},
    )
    assert load_resp.status_code == 200
    assert load_resp.json()["run_id"] == "web"
