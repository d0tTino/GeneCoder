import os
from pathlib import Path
from tests.test_cli import run_cli_command

import pytest

@pytest.mark.parametrize(
    "sim_name",
    ["illumina", "illumina_d2sim", "illumina_insilicoseq", "nanopore_d2sim", "nanopore_desp"],
)
def test_cli_decode_with_builtin_simulator(tmp_path: Path, sim_name: str):
    env = os.environ.copy()
    src_path = Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    input_file = tmp_path / "sim.txt"
    input_file.write_text("built-in simulator test")

    encode_result = run_cli_command(
        [
            "encode",
            "--input-files",
            str(input_file),
            "--output-dir",
            str(tmp_path),
            "--method",
            "base4_direct",
            "--fec",
            "triple_repeat",
        ],
        env=env,
    )
    assert encode_result.returncode == 0, encode_result.stderr
    fasta_file = tmp_path / "sim.txt.fasta"
    assert fasta_file.exists()

    decode_result = run_cli_command(
        [
            "decode",
            "--input-files",
            str(fasta_file),
            "--output-dir",
            str(tmp_path),
            "--method",
            "base4_direct",
            "--simulator",
            sim_name,
        ],
        env=env,
    )
    assert decode_result.returncode == 0, decode_result.stderr
    assert (
        f"Applied {sim_name} simulator before decoding." in decode_result.stdout
    )
