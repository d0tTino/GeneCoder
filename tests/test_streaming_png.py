import os
import time
from pathlib import Path

from genecoder.streaming import stream_encode_file, stream_decode_file


def test_streaming_png_roundtrip(tmp_path: Path, record_property: object) -> None:
    chunk_size = 1_048_576  # 1 MB
    total_size = chunk_size * 10
    png_data = b"\x89PNG\r\n\x1a\n" + os.urandom(total_size - 8)
    png_path = tmp_path / "dummy.png"
    png_path.write_bytes(png_data)

    encoded_file = tmp_path / "encoded.fasta"
    decoded_file = tmp_path / "decoded.png"

    start = time.perf_counter()
    stream_encode_file(
        str(png_path),
        str(encoded_file),
        header="method=base4_direct input_file=dummy.png",
        chunk_size=chunk_size,
    )
    enc_time = time.perf_counter() - start

    start = time.perf_counter()
    stream_decode_file(str(encoded_file), str(decoded_file), chunk_size=chunk_size)
    dec_time = time.perf_counter() - start

    record_property("encode_time_png", enc_time)
    record_property("decode_time_png", dec_time)

    assert decoded_file.read_bytes() == png_data
