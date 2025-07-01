import os
from pathlib import Path

import pytest

from genecoder.streaming import stream_encode_file, stream_decode_file

pytestmark = pytest.mark.skipif(
    os.environ.get("LOW_RESOURCE_CI") == "1",
    reason="skipping resource-intensive test on low-resource CI",
)


def test_stream_encode_decode_resume(tmp_path: Path) -> None:
    data = os.urandom(6 * 1024 * 1024)  # >5 MB
    input_file = tmp_path / "data.bin"
    input_file.write_bytes(data)
    fasta_file = tmp_path / "data.fasta"
    enc_manifest = fasta_file.with_suffix(".stream.manifest")

    header = "method=base4_direct input_file=data.bin"
    stream_encode_file(
        str(input_file),
        str(fasta_file),
        header=header,
        chunk_size=1_048_576,
        manifest_path=str(enc_manifest),
        resume=True,
    )

    decoded_file = tmp_path / "decoded.bin"
    dec_manifest = decoded_file.with_suffix(".stream.manifest")
    stream_decode_file(
        str(fasta_file),
        str(decoded_file),
        chunk_size=1_048_576,
        manifest_path=str(dec_manifest),
        resume=True,
    )

    assert decoded_file.read_bytes() == data
    assert enc_manifest.exists() and dec_manifest.exists()
    assert sum(1 for _ in enc_manifest.open()) > 0
    assert sum(1 for _ in dec_manifest.open()) > 0
