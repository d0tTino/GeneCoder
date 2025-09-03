import os
import pytest

from genecoder.streaming import stream_encode, stream_decode
from genecoder.encoders import encode_base4_direct, decode_base4_direct
from genecoder.reed_solomon_codec import (
    encode_data_rs,
    decode_data_rs,
    _HAS_REEDSOLO,
)
from genecoder.ldpc_codec import (
    encode_data_ldpc,
    decode_data_ldpc,
    _HAS_PYLDPC,
)
from genecoder.raptorq_codec import (
    encode_data_raptorq,
    decode_data_raptorq,
    _HAS_RAPTORQ,
)


@pytest.fixture
def large_binary_file(tmp_path):
    data = os.urandom(2_097_152)  # 2 MB to span multiple chunks
    path = tmp_path / "large.bin"
    path.write_bytes(data)
    return path, data

@pytest.mark.parametrize(
    "fec_name,encode_fn,decode_fn,available",
    [
        ("reed_solomon", encode_data_rs, decode_data_rs, _HAS_REEDSOLO),
        ("ldpc", encode_data_ldpc, decode_data_ldpc, _HAS_PYLDPC),
        ("raptorq", encode_data_raptorq, decode_data_raptorq, _HAS_RAPTORQ),
    ],
    ids=["reed_solomon", "ldpc", "raptorq"],
)
def test_stream_pipeline_roundtrip(fec_name, encode_fn, decode_fn, available):
    if not available:
        pytest.skip(f"{fec_name} not available")

    data = os.urandom(256)
    chunks = [data[:128], data[128:]]
    infos: list[object] = []

    def fec_enc(chunk: bytes):
        encoded, info = encode_fn(chunk)
        infos.append(info)
        return encoded, info

    dna_chunks = [chunk for _, chunk in stream_encode(chunks, encode_base4_direct, fec_encode=fec_enc)]

    def decode_direct(dna: str) -> bytes:
        return decode_base4_direct(dna)[0]

    def fec_dec(chunk: bytes, _info: object):
        info = infos.pop(0)
        return decode_fn(chunk, info)

    decoded_chunks = [chunk for _, chunk in stream_decode(dna_chunks, decode_direct, fec_decode=fec_dec)]

    assert b"".join(decoded_chunks) == data


def _chunk_reader(path: str, size: int):
    with open(path, "rb") as f:
        while True:
            chunk = f.read(size)
            if not chunk:
                break
            yield chunk


@pytest.mark.parametrize(
    "fec_name,encode_fn,decode_fn,available",
    [
        ("reed_solomon", encode_data_rs, decode_data_rs, _HAS_REEDSOLO),
        ("ldpc", encode_data_ldpc, decode_data_ldpc, _HAS_PYLDPC),
        ("raptorq", encode_data_raptorq, decode_data_raptorq, _HAS_RAPTORQ),
    ],
    ids=["reed_solomon", "ldpc", "raptorq"],
)
def test_stream_pipeline_large_file_roundtrip(
    tmp_path, large_binary_file, fec_name, encode_fn, decode_fn, available
):
    if not available:
        pytest.skip(f"{fec_name} not available")
    bin_path, data = large_binary_file
    chunk_size = 1_048_576  # 1 MB
    infos: list[object] = []

    def fec_enc(chunk: bytes):
        encoded, info = encode_fn(chunk)
        infos.append(info)
        return encoded, info

    dna_chunks = [
        chunk
        for _, chunk in stream_encode(
            _chunk_reader(str(bin_path), chunk_size),
            encode_base4_direct,
            fec_encode=fec_enc,
        )
    ]

    def decode_direct(dna: str) -> bytes:
        return decode_base4_direct(dna)[0]

    def fec_dec(chunk: bytes, _info: object):
        info = infos.pop(0)
        return decode_fn(chunk, info)

    decoded_chunks = [
        chunk for _, chunk in stream_decode(dna_chunks, decode_direct, fec_decode=fec_dec)
    ]

    assert b"".join(decoded_chunks) == data
