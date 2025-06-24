from pathlib import Path
import pytest

pytest.importorskip("cryptography")

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


def test_encrypt_roundtrip_key_file(tmp_path: Path) -> None:
    pytest.importorskip("cryptography")
    key_path = tmp_path / "key.bin"
    key_bytes = b"custom-key"
    key_path.write_bytes(key_bytes)
    data = b"via-keyfile"
    key = key_path.read_bytes()
    enc = encrypt_data(data, key=key)
    assert decrypt_data(enc, key=key) == data


def test_cli_encrypt_checksum_key_file(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("cryptography")
    key_path = tmp_path / "cli.key"
    key_path.write_bytes(b"cli-key")
    monkeypatch.setattr("genecoder.security._DEFAULT_KEY", key_path.read_bytes())

    src = tmp_path / "msg2.txt"
    src.write_text("secure keyfile")

    enc_res = run_cli_command([
        "encode",
        "--input-files",
        str(src),
        "--output-dir",
        str(tmp_path),
        "--method",
        "base4_direct",
        "--encrypt",
        "--checksum",
    ])
    assert enc_res.returncode == 0, enc_res.stderr
    fasta = tmp_path / "msg2.txt.fasta"
    assert fasta.exists()
    dec_res = run_cli_command([
        "decode",
        "--input-files",
        str(fasta),
        "--output-dir",
        str(tmp_path),
        "--method",
        "base4_direct",
        "--encrypt",
        "--checksum",
    ])
    assert dec_res.returncode == 0, dec_res.stderr
    out_file = tmp_path / "msg2.txt_decoded.bin"
    assert out_file.exists()
    assert out_file.read_text() == "secure keyfile"
