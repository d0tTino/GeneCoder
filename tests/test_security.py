from pathlib import Path

from genecoder.security import (
    encrypt_data,
    decrypt_data,
    compute_checksum,
    _DEFAULT_KEY,
)
from tests.test_cli import run_cli_command


def test_encrypt_roundtrip_random_nonce() -> None:
    data = b"hello"
    enc1 = encrypt_data(data, key=b"k")
    enc2 = encrypt_data(data, key=b"k")
    assert enc1 != enc2
    assert enc1.startswith(b"AESGCM1")
    assert decrypt_data(enc1, key=b"k") == data
    assert decrypt_data(enc2, key=b"k") == data


def test_checksum() -> None:
    data = b"abc"
    import hashlib

    expected = hashlib.sha256(data).hexdigest()
    assert compute_checksum(data) == expected


def _legacy_xor_encrypt(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def test_decrypt_legacy_format() -> None:
    data = b"legacy"
    legacy_enc = _legacy_xor_encrypt(data, _DEFAULT_KEY)
    assert decrypt_data(legacy_enc) == data


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
