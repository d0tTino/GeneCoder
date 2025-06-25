import os
from pathlib import Path
import pytest
from tests.test_cli import run_cli_command


@pytest.mark.parametrize("sim_name", ["d2sim", "dnarsim", "squigulator"])
def test_cli_simulator_fallback(tmp_path: Path, sim_name: str):
    env = os.environ.copy()
    src_path = Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / sim_name
    script.write_text("#!/bin/sh\nexit 1\n")
    script.chmod(0o755)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

    input_file = tmp_path / "in.txt"
    input_file.write_text("fallback test")

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
    fasta_file = tmp_path / "in.txt.fasta"
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
    output_file = tmp_path / "in.txt_decoded.bin"
    assert output_file.exists()
    assert output_file.read_text().startswith("fallback")
