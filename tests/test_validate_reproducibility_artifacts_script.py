from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_validator_script_fails_when_report_missing(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path("src").resolve())
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/validate_reproducibility_artifacts.py",
            "--artifact-root",
            str(tmp_path),
            "--mode",
            "bundle_sweep",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert proc.returncode != 0


def test_validator_script_passes_with_report(tmp_path: Path) -> None:
    (tmp_path / "manifest_index.json").write_text("{}", encoding="utf-8")
    report = {
        "summary": {
            "pass": True,
            "tolerance_violations": 0,
            "deterministic_violations": 0,
        }
    }
    (tmp_path / "reproducibility_report.json").write_text(
        json.dumps(report), encoding="utf-8"
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path("src").resolve())
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/validate_reproducibility_artifacts.py",
            "--artifact-root",
            str(tmp_path),
            "--mode",
            "bundle_sweep",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
