from pathlib import Path

from tests.test_cli import run_cli_command


def test_auto_ext_roundtrip(tmp_path: Path) -> None:
    input_file = tmp_path / "msg.txt"
    input_file.write_text("auto")

    enc_res = run_cli_command([
        "encode",
        "--input-files",
        str(input_file),
        "--output-dir",
        str(tmp_path),
        "--method",
        "base4_direct",
        "--auto-ext",
    ])
    assert enc_res.returncode == 0, enc_res.stderr

    encoded = tmp_path / "msg.txt.dna"
    assert encoded.exists()

    dec_res = run_cli_command([
        "decode",
        "--input-files",
        str(encoded),
        "--output-dir",
        str(tmp_path),
        "--method",
        "base4_direct",
        "--auto-ext",
    ])
    assert dec_res.returncode == 0, dec_res.stderr

    decoded = tmp_path / "msg.txt"
    assert decoded.exists()
    assert decoded.read_text() == "auto"

