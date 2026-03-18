from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from genecoder.pipeline import build_kpi_bundle
from tests.test_cli import run_cli_command


def test_build_kpi_bundle_includes_comparison_and_dashboard() -> None:
    run_schema = {
        "schema_version": "1.2",
        "run_id": "example-run",
        "profiles": {"encoding": "base4_direct", "simulation": "none", "decode": "base4_direct"},
        "seeds": {"global": 1, "encode": 1, "simulate": 1, "decode": 1},
        "runtime": {"total_seconds": 0.1, "encode_seconds": 0.01, "simulate_seconds": 0.02, "decode_seconds": 0.07},
        "stages": {
            "encode": {"metrics": {"gc_content": 0.5, "gc_variance": 0.0, "max_homopolymer": 2}},
            "simulate": {"metrics": {"substitutions": 0, "insertions": 0, "deletions": 0, "coverage": 1}},
            "decode": {"metrics": {"decode_success": True, "decode_success_rate": 1.0, "ecc_success_rates": {}}},
        },
        "outcome": {"metrics": {"ber": 0.0, "throughput": 1.0}},
        "constraint_outcomes": {"summary": None, "by_oligo": {}, "stages": []},
        "decode_outcomes": {"decode_success": True, "decode_success_rate": 1.0, "ecc_success_rates": {}},
        "provenance": {"source_format": "test", "generator": "test"},
    }

    bundle = build_kpi_bundle(run_schema, artifact_path="artifacts/runs/example-run/metrics.json")
    assert bundle["run_id"] == "example-run"
    assert "comparison" in bundle["kpis"]
    assert "dashboard" in bundle["kpis"]
    assert bundle["artifacts"]["run_schema"].endswith("metrics.json")


def test_cli_pipeline_emits_kpi_bundle_artifact(tmp_path: Path) -> None:
    input_file = tmp_path / "input.bin"
    output_file = tmp_path / "decoded.bin"
    input_file.write_bytes(b"hello")

    result = run_cli_command(
        [
            "pipeline",
            "--codec",
            "reverse",
            "--channel",
            "none",
            str(input_file),
            str(output_file),
            "--seed",
            "123",
        ]
    )
    assert result.returncode == 0, result.stderr

    metrics_path = Path(str(output_file) + ".json")
    kpi_path = metrics_path.with_suffix(".kpi.json")
    assert kpi_path.exists()
    payload = json.loads(kpi_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == output_file.stem
    assert payload["artifacts"]["run_schema"] == str(metrics_path)


def test_build_kpi_bundle_rejects_home_scoped_metrics_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home_dir = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home_dir)

    with pytest.raises(ValueError, match="run-scoped paths"):
        build_kpi_bundle(
            {
                "run_id": "example-run",
                "stages": {"decode": {"metrics": {"decode_success": True}}},
                "outcome": {},
            },
            artifact_path=str(home_dir / ".genecoder" / "metrics.json"),
        )


def test_metrics_kpi_schema_accepts_run_scoped_artifact() -> None:
    schema = json.loads(
        Path("configs/schema/metrics.kpi.schema.json").read_text(encoding="utf-8")
    )
    payload = build_kpi_bundle(
        {
            "run_id": "schema-run",
            "stages": {"decode": {"metrics": {"decode_success": True}}},
            "outcome": {"throughput": 1.0, "ber": 0.0},
        },
        artifact_path="artifacts/runs/schema-run/metrics.json",
    )

    assert list(Draft202012Validator(schema).iter_errors(payload)) == []
