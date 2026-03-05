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
        "illumina",
        "--illumina-profile",
        "miseq",
        "--seed",
        "7",
    ]

    result1 = run_cli_command(cmd)
    assert result1.returncode == 0, result1.stderr

    cmd[2] = str(out2)
    result2 = run_cli_command(cmd)
    assert result2.returncode == 0, result2.stderr

    import json

    metrics1 = json.loads(Path(str(out1) + ".json").read_text(encoding="utf-8"))
    metrics2 = json.loads(Path(str(out2) + ".json").read_text(encoding="utf-8"))
    for key in ("substitutions", "insertions", "deletions", "dropout_count", "coverage"):
        assert metrics1["outcome"]["metrics"].get(key) == metrics2["outcome"]["metrics"].get(key)



def test_pipeline_seed_reproducible_with_illumina_profile(tmp_path: Path) -> None:
    input_file = tmp_path / "data_profile.bin"
    input_file.write_bytes(b"seedtest-profile")

    out1 = tmp_path / "out_profile_1.bin"
    out2 = tmp_path / "out_profile_2.bin"

    cmd = [
        "pipeline",
        str(input_file),
        str(out1),
        "--codec",
        "reverse",
        "--channel",
        "illumina",
        "--illumina-profile",
        "miseq",
        "--seed",
        "42",
    ]

    result1 = run_cli_command(cmd)
    assert result1.returncode == 0, result1.stderr

    cmd[2] = str(out2)
    result2 = run_cli_command(cmd)
    assert result2.returncode == 0, result2.stderr

    import json

    metrics1 = json.loads(Path(str(out1) + ".json").read_text(encoding="utf-8"))
    metrics2 = json.loads(Path(str(out2) + ".json").read_text(encoding="utf-8"))

    for key in ("substitutions", "insertions", "deletions", "dropout_count", "coverage"):
        assert metrics1["outcome"]["metrics"].get(key) == metrics2["outcome"]["metrics"].get(key)
