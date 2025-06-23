from pathlib import Path
from tests.test_cli import run_cli_command


def test_cli_encryption_roundtrip(tmp_path: Path):
    key = '00' * 32
    input_file = tmp_path / 'secret.txt'
    input_file.write_text('top secret')

    encode_res = run_cli_command([
        'encode',
        '--input-files', str(input_file),
        '--output-dir', str(tmp_path),
        '--method', 'base4_direct',
        '--encryption-key', key,
    ])
    assert encode_res.returncode == 0, encode_res.stderr
    fasta_file = tmp_path / 'secret.txt.fasta'
    assert fasta_file.exists()

    decode_res = run_cli_command([
        'decode',
        '--input-files', str(fasta_file),
        '--output-dir', str(tmp_path),
        '--method', 'base4_direct',
        '--encryption-key', key,
    ])
    assert decode_res.returncode == 0, decode_res.stderr
    out_file = tmp_path / 'secret.txt_decoded.bin'
    assert out_file.exists()
    assert out_file.read_text() == 'top secret'
