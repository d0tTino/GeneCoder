from pathlib import Path

from genecoder.synthesis import SynthesisConstraints, validate_sequence
from genecoder.formats import to_fasta


import os
import subprocess
import sys
from pathlib import Path as SysPath

PROJECT_ROOT = SysPath(__file__).parent.parent


def run_cli_command(command_args: list[str], env=None) -> subprocess.CompletedProcess:
    if env is None:
        env = os.environ.copy()
        src_path = PROJECT_ROOT / "src"
        env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    full_command = [sys.executable, "-m", "genecoder.cli"] + command_args
    return subprocess.run(full_command, capture_output=True, text=True, env=env, cwd=PROJECT_ROOT)


def test_validate_sequence_pass():
    constraints = SynthesisConstraints(min_length=5, max_length=10, max_homopolymer=2)
    assert validate_sequence("ACGTAC", constraints)


def test_validate_sequence_fail_length():
    constraints = SynthesisConstraints(min_length=5, max_length=10, max_homopolymer=2)
    assert not validate_sequence("AC", constraints)


def test_validate_sequence_fail_homopolymer():
    constraints = SynthesisConstraints(min_length=5, max_length=10, max_homopolymer=2)
    assert not validate_sequence("AAACCC", constraints)


def test_export_csv_and_analysis_warnings(tmp_path: Path):
    # Create input files
    f1 = tmp_path / "a.txt"
    f1.write_text("hello")
    outdir = tmp_path / "out"
    outdir.mkdir()
    csv_file = tmp_path / "order.csv"

    cmd = [
        "encode",
        "--input-files",
        str(f1),
        "--output-dir",
        str(outdir),
        "--method",
        "base4_direct",
        "--export-csv",
        str(csv_file),
    ]
    result = run_cli_command(cmd)
    assert result.returncode == 0
    assert csv_file.exists()
    content = csv_file.read_text()
    assert "Name,Sequence" in content

    # Create fasta with long homopolymer
    seq = "A" * 10
    fasta = outdir / "bad.fasta"
    fasta.write_text(to_fasta(seq, "seq1"))

    cmd = ["analyze", "--input-files", str(fasta)]
    result = run_cli_command(cmd)
    assert result.returncode == 0
    assert "homopolymer" in result.stderr
