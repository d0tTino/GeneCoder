import os
from pathlib import Path
from typing import Iterator
import json

import pytest

from genecoder.streaming import (
    stream_encode_file,
    stream_decode_file,
    encode_base4_direct,
    decode_base4_direct,
)


def test_stream_encode_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = os.urandom(150_000)
    input_file = tmp_path / "in.bin"
    encoded_file = tmp_path / "out.fasta"
    input_file.write_bytes(data)
    manifest = encoded_file.with_suffix(".stream.manifest")
    header = "method=base4_direct input_file=in.bin"

    count = 0
    orig_encode = encode_base4_direct

    def fail_after_two(*args: object, **kwargs: object) -> Iterator[str]:
        nonlocal count
        for chunk in orig_encode(*args, **kwargs):
            count += 1
            if count == 2:
                raise RuntimeError("stop")
            yield chunk

    monkeypatch.setattr("genecoder.streaming.encode_base4_direct", fail_after_two)
    with pytest.raises(RuntimeError):
        stream_encode_file(
            str(input_file),
            str(encoded_file),
            header=header,
            chunk_size=50_000,
            manifest_path=str(manifest),
        )
    assert manifest.exists()
    assert sum(1 for _ in manifest.open()) == 1

    monkeypatch.setattr("genecoder.streaming.encode_base4_direct", orig_encode)
    stream_encode_file(
        str(input_file),
        str(encoded_file),
        header=header,
        chunk_size=50_000,
        manifest_path=str(manifest),
        resume=True,
    )

    lines = [json.loads(line) for line in manifest.open()]
    assert len(lines) == 3
    assert lines[0]["offset"] == 0 and lines[-1]["offset"] == 100_000

    decoded = tmp_path / "decoded.bin"
    stream_decode_file(
        str(encoded_file),
        str(decoded),
        chunk_size=50_000,
    )
    assert decoded.read_bytes() == data


def test_stream_decode_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = os.urandom(120_000)
    bin_file = tmp_path / "data.bin"
    bin_file.write_bytes(data)
    fasta = tmp_path / "data.fasta"
    header = "method=base4_direct input_file=data.bin"
    stream_encode_file(str(bin_file), str(fasta), header=header, chunk_size=40_000)

    decoded = tmp_path / "decoded.bin"
    manifest = decoded.with_suffix(".stream.manifest")

    count = 0
    orig_decode = decode_base4_direct

    def fail_after_two(*args: object, **kwargs: object) -> Iterator[tuple[bytes, list[int]]]:
        nonlocal count
        for chunk, errs in orig_decode(*args, **kwargs):
            count += 1
            if count == 2:
                raise RuntimeError("fail")
            yield chunk, errs

    monkeypatch.setattr("genecoder.streaming.decode_base4_direct", fail_after_two)
    with pytest.raises(RuntimeError):
        stream_decode_file(
            str(fasta),
            str(decoded),
            chunk_size=40_000,
            manifest_path=str(manifest),
        )
    assert sum(1 for _ in open(manifest)) == 1

    monkeypatch.setattr("genecoder.streaming.decode_base4_direct", orig_decode)
    stream_decode_file(
        str(fasta),
        str(decoded),
        chunk_size=40_000,
        manifest_path=str(manifest),
        resume=True,
    )
    assert decoded.read_bytes() == data
    lines = [json.loads(line) for line in open(manifest)]
    assert len(lines) == 3
