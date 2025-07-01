import json
from pathlib import Path
import os

from tests.test_cli import run_cli_command


def test_cli_writes_manifest(tmp_path: Path) -> None:
    input_file = tmp_path / "data.txt"
    input_file.write_text("hi")
    result = run_cli_command([
        "encode",
        "--input-files",
        str(input_file),
        "--output-dir",
        str(tmp_path),
        "--method",
        "base4_direct",
    ])
    assert result.returncode == 0, result.stderr
    manifest = tmp_path / "data.txt.manifest.json"
    assert manifest.exists()
    data = json.loads(manifest.read_text())
    assert data["file"] == os.path.basename(input_file.as_posix())
    assert data["encoding_parameters"]["method"] == "base4_direct"
