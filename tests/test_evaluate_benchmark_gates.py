from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_evaluate_benchmark_gates_from_artifact_json(tmp_path: Path) -> None:
    artifact = tmp_path / "throughput.kpi.json"
    artifact.write_text(
        json.dumps(
            {
                "benchmark": "throughput",
                "parsed_metrics": {
                    "results": [
                        {
                            "profile": "base4_clean_256kb",
                            "throughput": 1.9,
                            "BER": 0.0,
                            "decode_success": True,
                            "runtime_per_mb": 1.0,
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "gate.json"

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate_benchmark_gates.py",
            "--benchmark",
            "throughput",
            "--artifact-json",
            str(artifact),
            "--output-json",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert report["evidence_artifact"] == str(artifact)
    assert report["parsed_metrics"]["results"][0]["throughput"] == 1.9


def test_evaluate_benchmark_gates_rejects_home_scoped_artifact(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "home" / ".genecoder" / "throughput.kpi.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps({"parsed_metrics": {"results": []}}), encoding="utf-8")
    output = tmp_path / "gate.json"

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate_benchmark_gates.py",
            "--benchmark",
            "throughput",
            "--artifact-json",
            str(artifact),
            "--output-json",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "run-scoped artifacts" in proc.stderr or "run-scoped artifacts" in proc.stdout
    assert not output.exists()
