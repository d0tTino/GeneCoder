from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _venv_paths(root: Path) -> tuple[Path, Path]:
    """Return (python_bin, genecli_bin) for the created virtual environment."""

    bin_dir = "Scripts" if os.name == "nt" else "bin"
    python_bin = root / bin_dir / "python"
    genecli_bin = root / bin_dir / "genecli"
    return python_bin, genecli_bin


def test_starter_plugin_present_in_catalog(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    venv_dir = tmp_path / "starter-plugin-venv"

    subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
    python_bin, genecli_bin = _venv_paths(venv_dir)

    subprocess.check_call([python_bin, "-m", "pip", "install", "-e", str(project_root)])
    subprocess.check_call(
        [
            python_bin,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "-e",
            str(project_root / "plugins-examples" / "starter_plugin"),
        ]
    )

    env = dict(os.environ)
    env.setdefault("GENECODER_PLUGIN_CATALOG_URL", "")
    env.setdefault("PYTHONWARNINGS", "ignore")

    result = subprocess.run(
        [genecli_bin, "plugin", "list"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "starter-template" in result.stdout
