from pathlib import Path

from tests.test_cli import run_cli_command


def test_pipeline_seed_reproducible(tmp_path: Path) -> None:
    input_file = tmp_path / "data.bin"
    input_file.write_bytes(b"seedtest")

    out1 = tmp_path / "out1.bin"
    out2 = tmp_path / "out2.bin"

    cmd = [
        "pipeline",
        str(input_file),
        str(out1),
        "--codec",
        "reverse",
        "--channel",
        "simple",
        "--sub-rate",
        "0.5",
        "--seed",
        "7",
    ]

    result1 = run_cli_command(cmd)
    assert result1.returncode == 0, result1.stderr

    cmd[2] = str(out2)
    result2 = run_cli_command(cmd)
    assert result2.returncode == 0, result2.stderr

    assert out1.read_bytes() == out2.read_bytes()
