import json
from pathlib import Path
from tests.test_cli import run_cli_command


def test_encode_capsule_contents(tmp_path: Path) -> None:
    input_file = tmp_path / "msg.txt"
    input_file.write_text("capsule test")

    output_dir = tmp_path / "out"
    output_dir.mkdir()

    capsule_path = tmp_path / "seq.capsule"

    result = run_cli_command(
        [
            "encode",
            "--input-files",
            str(input_file),
            "--output-dir",
            str(output_dir),
            "--method",
            "base4_direct",
            "--capsule",
            str(capsule_path),
        ]
    )
    assert result.returncode == 0, result.stderr
    assert capsule_path.exists()

    data = json.loads(capsule_path.read_text())
    assert data["version"] == 1
    assert "method=base4_direct" in data["header"]
    assert data["metadata"]["input_file"] == "msg.txt"
    assert data["metadata"]["method"] == "base4_direct"
    assert isinstance(data["sequence"], str) and data["sequence"]


def test_encode_capsule_multiple_inputs_error(tmp_path: Path) -> None:
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("a")
    f2.write_text("b")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    capsule_path = tmp_path / "multi.capsule"

    result = run_cli_command(
        [
            "encode",
            "--input-files",
            str(f1),
            str(f2),
            "--output-dir",
            str(out_dir),
            "--method",
            "base4_direct",
            "--capsule",
            str(capsule_path),
        ]
    )
    assert result.returncode != 0
    assert "--capsule can only be used" in result.stderr
