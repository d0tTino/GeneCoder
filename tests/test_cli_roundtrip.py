from pathlib import Path
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

