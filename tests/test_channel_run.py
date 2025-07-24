from pathlib import Path
import pytest
from tests.test_cli import run_cli_command

pytest.importorskip("yaml")


def test_channel_run(tmp_path: Path) -> None:
    inp = tmp_path / "in.txt"
    inp.write_text("hello")
    enc = run_cli_command([
        "encode",
        "--input-files",
        str(inp),
        "--output-dir",
        str(tmp_path),
        "--method",
        "base4_direct",
    ])
    assert enc.returncode == 0, enc.stderr
    fasta = tmp_path / "in.txt.fasta"
    cfg = tmp_path / "cfg.yml"
    out_path = tmp_path / "out.fasta"
    cfg.write_text(
        f"input: {fasta}\noutput: {out_path}\nsimulators:\n  - simple\n"
        "synthesis:\n  min_length: 1\n  max_length: 500\n  max_homopolymer: 10\n"
    )
    res = run_cli_command(["channel", "run", str(cfg)])
    assert res.returncode == 0, res.stderr
    assert out_path.exists()

