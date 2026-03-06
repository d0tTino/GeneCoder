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
                    "base4_encode_mb_s": 2.5,
                    "base4_decode_mb_s": 5.0,
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
    assert report["parsed_metrics"]["base4_encode_mb_s"] == 2.5
