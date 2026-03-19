from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from scripts.generate_competitor_report import collect_results, load_yaml, validate_matrix

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "benchmarks" / "competitor_matrix.yaml"
SCHEMA_PATH = ROOT / "configs" / "schema" / "benchmark_competitor_matrix.schema.json"


def test_competitor_matrix_matches_schema() -> None:
    matrix = yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(matrix))
    assert errors == []
    validate_matrix(matrix)


def test_collect_results_falls_back_to_fixture_baselines(tmp_path: Path) -> None:
    matrix = load_yaml(MATRIX_PATH)
    rows = collect_results(matrix, tmp_path)

    assert rows
    gene_rows = [row for row in rows if row["tool"] == "GeneCoder"]
    fixture_rows = [row for row in rows if row["source_type"] == "fixture_baseline"]
    assert gene_rows
    assert fixture_rows
    assert all("throughput_mb_s" in row for row in rows)


def test_collect_results_prefers_runtime_artifacts(tmp_path: Path) -> None:
    matrix = load_yaml(MATRIX_PATH)
    runtime_path = tmp_path / "external" / "baseline_dna_clean_roundtrip_256kb.json"
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text(
        json.dumps(
            {
                "normalized_outputs": {
                    "tool": "BaselineDNA",
                    "throughput_mb_s": 9.99,
                    "bit_error_rate": 0.0,
                    "decode_success": True,
                    "latency_ms": 25.0,
                    "peak_memory_mb": 44.0,
                    "notes": "runtime artifact",
                }
            }
        ),
        encoding="utf-8",
    )

    rows = collect_results(matrix, tmp_path)
    runtime_row = next(
        row
        for row in rows
        if row["tool"] == "BaselineDNA" and row["scenario"] == "clean_roundtrip_256kb"
    )
    assert runtime_row["source_type"] == "runtime_artifact"
    assert runtime_row["throughput_mb_s"] == 9.99


def test_generate_competitor_report_script_outputs_markdown_and_chart(tmp_path: Path) -> None:
    output = tmp_path / "competitor_report.md"
    chart = tmp_path / "competitor_report.svg"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/generate_competitor_report.py",
            "--matrix",
            str(MATRIX_PATH),
            "--results-root",
            str(tmp_path),
            "--output",
            str(output),
            "--chart",
            str(chart),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert output.exists()
    assert chart.exists()
    report_text = output.read_text(encoding="utf-8")
    assert "# External Benchmark Comparison Report" in report_text
    assert "fixture_baseline" in report_text
    assert "clean_roundtrip_256kb" in report_text
