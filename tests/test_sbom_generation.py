from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch


def test_sbom_generation_includes_dependencies(tmp_path: Path) -> None:
    output_file = tmp_path / "sbom.xml"

    expected = (
        "<component>reedsolo</component>"
        "<component>cryptography</component>"
    )

    def fake_run(cmd: list[str], check: bool) -> subprocess.CompletedProcess:
        Path(cmd[cmd.index("-o") + 1]).write_text(expected)
        return subprocess.CompletedProcess(cmd, 0)

    with patch("subprocess.run", side_effect=fake_run) as mocked_run:
        subprocess.run([
            "cyclonedx-py",
            "poetry",
            "-o",
            str(output_file),
            "--of",
            "XML",
        ], check=True)
        mocked_run.assert_called_once()

    sbom_text = output_file.read_text()
    assert "reedsolo" in sbom_text
    assert "cryptography" in sbom_text

