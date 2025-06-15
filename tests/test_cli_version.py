import os
import subprocess
import sys
from pathlib import Path

import genecoder

PROJECT_ROOT = Path(__file__).parent.parent


def test_cli_version(tmp_path: Path):
    """Install the package and verify the CLI returns the version."""
    venv_dir = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    bin_dir = "Scripts" if os.name == "nt" else "bin"
    pip_path = venv_dir / bin_dir / "pip"
    genecoder_path = venv_dir / bin_dir / "genecoder"

    subprocess.run([str(pip_path), "install", "-U", "pip", "setuptools", "wheel"], check=True)
    subprocess.run([str(pip_path), "install", "matplotlib", "flet>=0.28,<0.29", "reedsolo"], check=True)

    subprocess.run([
        str(pip_path),
        "install",
        "--no-deps",
        str(PROJECT_ROOT),
    ], check=True)

    result = subprocess.run(
        [str(genecoder_path), "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == f"GeneCoder {genecoder.__version__}"

