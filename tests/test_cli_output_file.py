import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_cli_command_cwd(command_args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    src_path = PROJECT_ROOT / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    full_command = [sys.executable, "-m", "genecoder.cli"] + command_args
    return subprocess.run(full_command, capture_output=True, text=True, env=env, cwd=cwd)


def test_encode_output_file_no_directory(tmp_path: Path):
    input_file = tmp_path / "in.txt"
    input_file.write_text("hello")

    result = run_cli_command_cwd([
        "encode",
        "--input-files",
        input_file.name,
        "--output-file",
        "out.fasta",
        "--method",
        "base4_direct",
    ], tmp_path)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "out.fasta").exists()


def test_decode_output_file_no_directory(tmp_path: Path):
    # first encode
    input_file = tmp_path / "in.txt"
    input_file.write_text("abc")
    encode_res = run_cli_command_cwd([
        "encode",
        "--input-files",
        input_file.name,
        "--output-file",
        "enc.fasta",
        "--method",
        "base4_direct",
    ], tmp_path)
    assert encode_res.returncode == 0, encode_res.stderr

    # now decode
    result = run_cli_command_cwd([
        "decode",
        "--input-files",
        "enc.fasta",
        "--output-file",
        "decoded.bin",
        "--method",
        "base4_direct",
    ], tmp_path)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "decoded.bin").exists()

