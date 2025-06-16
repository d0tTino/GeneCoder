from pathlib import Path
import os
from tests.test_cli import run_cli_command


def test_cli_encode_decode_roundtrip(tmp_path: Path):
    input_file = tmp_path / "round.txt"
    input_file.write_text("cli round trip")

    # Encode
    encode_result = run_cli_command([
        "encode",
        "--input-files",
        str(input_file),
        "--output-dir",
        str(tmp_path),
        "--method",
        "base4_direct",
    ])
    assert encode_result.returncode == 0, encode_result.stderr
    fasta_file = tmp_path / "round.txt.fasta"
    assert fasta_file.exists()

    # Decode
    decode_result = run_cli_command([
        "decode",
        "--input-files",
        str(fasta_file),
        "--output-dir",
        str(tmp_path),
        "--method",
        "base4_direct",
    ])
    assert decode_result.returncode == 0, decode_result.stderr
    output_file = tmp_path / "round.txt_decoded.bin"
    assert output_file.exists()
    assert output_file.read_text() == "cli round trip"


def test_cli_decode_with_simulator(tmp_path: Path):
    env = os.environ.copy()
    src_path = Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    input_file = tmp_path / "sim.txt"
    input_file.write_text("nanopore test")

    # Encode with triple_repeat FEC for robustness
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

    # Decode using the nanopore simulator
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
            "nanopore",
        ],
        env=env,
    )
    assert decode_result.returncode == 0, decode_result.stderr
    output_file = tmp_path / "sim.txt_decoded.bin"
    assert output_file.exists()
    assert output_file.read_text() == "nanopore test"

