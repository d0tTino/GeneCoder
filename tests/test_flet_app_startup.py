import os
import sys
import subprocess
import textwrap
import time
from pathlib import Path

import pytest

ft = pytest.importorskip("flet")

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_flet_app_main_starts(tmp_path: Path):
    script = textwrap.dedent(
        """
        import flet as ft
        from genecoder.flet_app import main
        ft.app(target=main, view=ft.AppView.FLET_APP_HIDDEN, port=0)
        """
    )
    script_file = tmp_path / "run_app.py"
    script_file.write_text(script)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.Popen([sys.executable, str(script_file)], env=env)
    time.sleep(2)
    assert proc.poll() is None
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
