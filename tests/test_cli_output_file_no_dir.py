import os
import subprocess
import sys
from pathlib import Path

from tests.test_cli import PROJECT_ROOT
from src.genecoder.encoders import encode_base4_direct
from src.genecoder.formats import to_fasta


def _run_cli(command_args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    src_path = PROJECT_ROOT / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [sys.executable, "-m", "genecoder.cli"] + command_args
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=cwd)


def test_encode_output_file_no_directory(tmp_path: Path) -> None:
    input_file = tmp_path / "input.txt"
    input_file.write_text("hello")
    result = _run_cli([
        "encode",
        "--input-files",
        str(input_file),
        "--output-file",
        "out.fasta",
        "--method",
        "base4_direct",
    ], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "out.fasta").exists()


def test_decode_output_file_no_directory(tmp_path: Path) -> None:
    data = b"decode-test"
    dna = encode_base4_direct(data)
    fasta = to_fasta(dna, "method=base4_direct input_file=in.bin")
    fasta_file = tmp_path / "seq.fasta"
    fasta_file.write_text(fasta)
    result = _run_cli([
        "decode",
        "--input-files",
        str(fasta_file),
        "--output-file",
        "out.bin",
        "--method",
        "base4_direct",
    ], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    out_path = tmp_path / "out.bin"
    assert out_path.exists()
    assert out_path.read_bytes() == data
