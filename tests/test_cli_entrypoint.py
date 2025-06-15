import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_genecoder_version_entrypoint(tmp_path: Path) -> None:
    env_dir = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(env_dir)], check=True)

    bindir = "Scripts" if os.name == "nt" else "bin"
    pip = env_dir / bindir / ("pip.exe" if os.name == "nt" else "pip")

    subprocess.run([str(pip), "install", "-e", str(PROJECT_ROOT)], check=True)

    env = os.environ.copy()
    env["PATH"] = str(env_dir / bindir) + os.pathsep + env.get("PATH", "")
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")

    subprocess.run(["genecoder", "--version"], check=True, env=env)
