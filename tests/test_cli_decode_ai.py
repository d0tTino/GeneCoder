import json
from pathlib import Path

import pytest

from tests.test_cli import run_cli_command  # type: ignore

pytest.importorskip("dnaformer")
from genecoder.dnaformer_codec import encode_data_dnaformer


def test_decode_ai_cli(temp_dir: Path) -> None:
    data = b"decode ai"
    encoded, info = encode_data_dnaformer(data)
    enc_file = temp_dir / "enc.bin"
    enc_file.write_bytes(encoded)
    info_file = temp_dir / "info.json"
    info_file.write_text(json.dumps(info))
    out_file = temp_dir / "out.bin"

    result = run_cli_command(
        [
            "decode-ai",
            "--encoded",
            str(enc_file),
            "--info",
            str(info_file),
            "--output",
            str(out_file),
        ]
    )
    assert result.returncode == 0
    assert out_file.read_bytes() == data

