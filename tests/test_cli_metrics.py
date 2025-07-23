from pathlib import Path

from tests.test_cli import run_cli_command


def test_encode_outputs_metrics(tmp_path: Path) -> None:
    input_file = tmp_path / "msg.txt"
    input_file.write_text("metrics")

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
    assert "Final GC content" in result.stdout
    assert "Final max homopolymer length" in result.stdout
