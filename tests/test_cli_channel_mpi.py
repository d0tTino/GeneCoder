import os
import shutil
from pathlib import Path

import pytest
from tests.test_cli import run_cli_command

pytest.importorskip("mpi4py")
if shutil.which("mpiexec") is None:
    pytest.skip("mpiexec not available", allow_module_level=True)


def create_fasta(path: Path, seq: str = "ACGT", header: str = "seq") -> None:
    from src.genecoder.formats import to_fasta
    path.write_text(to_fasta(seq, header))


def test_channel_cli_mpi(tmp_path: Path) -> None:
    input_fasta = tmp_path / "in.fasta"
    create_fasta(input_fasta)
    output_fasta = tmp_path / "out.fasta"
    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"
    result = run_cli_command(
        [
            "channel",
            "--input-file",
            str(input_fasta),
            "--output-file",
            str(output_fasta),
            "--simulator",
            "simple",
            "--min-length",
            "1",
            "--mpi",
            "--mpi-workers",
            "2",
        ],
        env=env,
    )
    assert result.returncode == 0, result.stderr
