from pathlib import Path

from genecoder.security import encrypt_data, decrypt_data, compute_checksum
from tests.test_cli import run_cli_command


def test_encrypt_roundtrip() -> None:
    data = b"hello"
    enc = encrypt_data(data)
    dec = decrypt_data(enc)
    assert dec == data


def test_checksum() -> None:
    data = b"abc"
    import hashlib

    expected = hashlib.sha256(data).hexdigest()
    assert compute_checksum(data) == expected


def test_cli_encrypt_checksum_roundtrip(tmp_path: Path) -> None:
    src = tmp_path / "msg.txt"
    src.write_text("secure message")

    enc_res = run_cli_command(
        [
            "encode",
            "--input-files",
            str(src),
            "--output-dir",
            str(tmp_path),
            "--method",
            "base4_direct",
            "--encrypt",
            "--checksum",
        ]
    )
    assert enc_res.returncode == 0, enc_res.stderr

    fasta = tmp_path / "msg.txt.fasta"
    assert fasta.exists()

    dec_res = run_cli_command(
        [
            "decode",
            "--input-files",
            str(fasta),
            "--output-dir",
            str(tmp_path),
            "--method",
            "base4_direct",
            "--encrypt",
            "--checksum",
        ]
    )
    assert dec_res.returncode == 0, dec_res.stderr
    out_file = tmp_path / "msg.txt_decoded.bin"
    assert out_file.exists()
    assert out_file.read_text() == "secure message"
