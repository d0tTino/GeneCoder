import os
import time
from genecoder.encoders import encode_base4_direct, decode_base4_direct


def _chunk_reader(path: str, size: int):
    with open(path, "rb") as f:
        while True:
            chunk = f.read(size)
            if not chunk:
                break
            yield chunk


def test_streaming_resume_large_file(tmp_path):
    chunk_size = 1_048_576  # 1 MB
    data = os.urandom(chunk_size * 12)
    bin_path = tmp_path / "large.bin"
    bin_path.write_bytes(data)

    gen = encode_base4_direct(_chunk_reader(bin_path, chunk_size), stream=True)
    first_chunk = next(gen)
    remaining_chunks = list(gen)
    dna_chunks = [first_chunk] + remaining_chunks

    dec_gen = decode_base4_direct(dna_chunks, stream=True)
    first_bytes, _ = next(dec_gen)
    rest = b"".join(part for part, _ in dec_gen)
    decoded = first_bytes + rest

    assert decoded == data


def test_streaming_roundtrip_10mb_runtime(tmp_path, record_property):
    chunk_size = 1_048_576  # 1 MB
    data = os.urandom(chunk_size * 10)
    bin_path = tmp_path / "ten_mb.bin"
    bin_path.write_bytes(data)

    start = time.perf_counter()
    dna_chunks = list(
        encode_base4_direct(_chunk_reader(bin_path, chunk_size), stream=True)
    )
    enc_time = time.perf_counter() - start

    start = time.perf_counter()
    decoded = b"".join(
        chunk for chunk, _ in decode_base4_direct(dna_chunks, stream=True)
    )
    dec_time = time.perf_counter() - start

    # record runtimes to help detect performance regressions
    record_property("encode_time", enc_time)
    record_property("decode_time", dec_time)
    assert decoded == data
