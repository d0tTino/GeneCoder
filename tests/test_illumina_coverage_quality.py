from __future__ import annotations

import json
from pathlib import Path

from tests.test_cli import run_cli_command


def test_channel_calibrate_writes_expected_artifacts(tmp_path: Path) -> None:
    dataset = {
        "profile": "illumina_hiseq",
        "baseline": [
            {
                "id": "b1",
                "original": "A" * 200,
                "observed": "A" * 199 + "C",
            },
            {"id": "b2", "original": "TTTT", "observed": "TTTT"},
        ],
        "calibrated": [
            {"id": "c1", "original": "A" * 200, "observed": "A" * 200},
            {"id": "c2", "original": "TTTT", "observed": "TTTT"},
        ],
    }
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

    output_root = tmp_path / "artifacts"
    result = run_cli_command(
        [
            "channel",
            "calibrate",
            "--dataset",
            str(dataset_path),
            "--profile",
            "illumina_hiseq",
            "--output-root",
            str(output_root),
            "--date",
            "2026-01-15",
        ]
    )

    assert result.returncode == 0, result.stderr
    artifact_dir = output_root / "illumina_hiseq" / "2026-01-15"
    assert artifact_dir.exists()
    assert (artifact_dir / "dataset_manifest.json").exists()
    assert (artifact_dir / "baseline_metrics.json").exists()
    assert (artifact_dir / "calibrated_metrics.json").exists()
    deviation = json.loads((artifact_dir / "deviation_summary.json").read_text(encoding="utf-8"))
    assert "threshold_evaluation" in deviation
    assert deviation["threshold_evaluation"]["passed"] is True
