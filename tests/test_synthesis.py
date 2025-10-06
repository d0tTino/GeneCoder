from pathlib import Path
import importlib.util

from genecoder.synthesis import SynthesisConstraints, validate_sequence
from genecoder.formats import to_fasta
import pytest


import os
import subprocess
import sys
from pathlib import Path as SysPath

PROJECT_ROOT = SysPath(__file__).parent.parent
try:
    CRYPTOGRAPHY_AVAILABLE = importlib.util.find_spec("cryptography") is not None
except (ImportError, ValueError):
    CRYPTOGRAPHY_AVAILABLE = False


def run_cli_command(command_args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    if env is None:
        env = os.environ.copy()
        src_path = PROJECT_ROOT / "src"
        env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    full_command = [sys.executable, "-m", "genecoder.cli"] + command_args
    return subprocess.run(full_command, capture_output=True, text=True, env=env, cwd=PROJECT_ROOT)


def test_validate_sequence_pass() -> None:
    constraints = SynthesisConstraints(min_length=5, max_length=10, max_homopolymer=2)
    assert validate_sequence("ACGTAC", constraints)


def test_validate_sequence_fail_length() -> None:
    constraints = SynthesisConstraints(min_length=5, max_length=10, max_homopolymer=2)
    assert not validate_sequence("AC", constraints)


def test_validate_sequence_fail_homopolymer() -> None:
    constraints = SynthesisConstraints(min_length=5, max_length=10, max_homopolymer=2)
    assert not validate_sequence("AAACCC", constraints)


def test_validate_sequence_gc_boundaries_accept() -> None:
    constraints = SynthesisConstraints(min_length=1, max_length=30)
    assert validate_sequence("GCGATACGATACGATACGAT", constraints)  # 45% GC
    assert validate_sequence("GCGATGCGATGCGATACGAT", constraints)  # 55% GC


def test_validate_sequence_gc_outside_reject() -> None:
    constraints = SynthesisConstraints(min_length=1, max_length=30)
    assert not validate_sequence("GCGATACATA", constraints)  # 40% GC
    assert not validate_sequence("GCGATGCGAT", constraints)  # 60% GC


def test_constraints_invalid_min_length() -> None:
    with pytest.raises(ValueError):
        SynthesisConstraints(min_length=0, max_length=10)


def test_constraints_negative_min_length() -> None:
    with pytest.raises(ValueError):
        SynthesisConstraints(min_length=-1, max_length=10)


def test_constraints_invalid_max_length() -> None:
    with pytest.raises(ValueError):
        SynthesisConstraints(min_length=5, max_length=0)


def test_constraints_negative_max_length() -> None:
    with pytest.raises(ValueError):
        SynthesisConstraints(min_length=5, max_length=-1)


def test_constraints_min_gt_max() -> None:
    with pytest.raises(ValueError):
        SynthesisConstraints(min_length=10, max_length=5)


def test_constraints_defaults() -> None:
    constraints = SynthesisConstraints()
    assert constraints.max_homopolymer == 3
    assert constraints.gc_min == pytest.approx(0.45)
    assert constraints.gc_max == pytest.approx(0.55)


def test_validate_sequence_homopolymer_thresholds() -> None:
    constraints = SynthesisConstraints(min_length=1, max_length=30)
    assert validate_sequence("AAACGCGCTA", constraints)
    assert not validate_sequence("AAAACGCGCT", constraints)


@pytest.mark.skipif(
    not CRYPTOGRAPHY_AVAILABLE,
    reason="cryptography dependency is required for CLI encode/analyze",
)
def test_export_csv_and_analysis_warnings(tmp_path: Path) -> None:
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
