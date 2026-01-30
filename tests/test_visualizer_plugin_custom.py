import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_cli import run_cli_command

pytest.importorskip("cryptography")


def test_visualizer_plugin_list(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "temp_viz_pkg"
    pkg_dir.mkdir()
    viz_mod = pkg_dir / "temp_viz"
    viz_mod.mkdir()
    (viz_mod / "__init__.py").write_text(
        """
from typing import Callable
from genecoder.api import Visualizer

class TempViz(Visualizer):
    def visualize(self, sequence: str, /, **kwargs: object) -> str:
        return sequence

def register(register_visualizer: Callable[[str, type[Visualizer]], None]) -> None:
    register_visualizer("temp_viz", TempViz)
"""
    )
    meta_mod = pkg_dir / "temp_viz_meta"
    meta_mod.mkdir()
    (meta_mod / "__init__.py").write_text(
        """
PLUGIN_METADATA = {
    "name": "temp-genecoder-visualizer",
    "version": "0.1.0",
    "interfaces": ["visualizer"],
    "license": "MIT",
}

def register(register_codec):
    pass
"""
    )
    (pkg_dir / "pyproject.toml").write_text(
        """
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "temp-genecoder-visualizer"
version = "0.1.0"

[project.entry-points."genecoder.visualizers"]
temp_viz = "temp_viz"

[project.entry-points."genecoder.plugins"]
temp-genecoder-visualizer = "temp_viz_meta"

[tool.setuptools.packages.find]
include = ["temp_viz", "temp_viz_meta"]
"""
    )
    subprocess.check_call([sys.executable, "-m", "pip", "install", str(pkg_dir), "--no-deps"])
    try:
        env = os.environ.copy()
        src_path = Path(__file__).resolve().parents[1] / "src"
        env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
        result = run_cli_command(["plugin", "list"], env=env)
        assert result.returncode == 0
        assert "temp-genecoder-visualizer" in result.stdout
    finally:
        subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", "temp-genecoder-visualizer"])
