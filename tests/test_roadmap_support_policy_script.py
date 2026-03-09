from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_roadmap_support_policy_script() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "check_roadmap_support_policy.py")],
        cwd=repo_root,
        env={**os.environ, "PYTHONPATH": str(repo_root / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
