import os
import pytest

from genecoder.stream_pipeline import stream_encode, stream_decode
from genecoder.encoders import encode_base4_direct, decode_base4_direct
from genecoder.hamming_codec import encode_data_with_hamming, decode_data_with_hamming
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
from genecoder.fountain_codec import (
    encode_data_fountain,
    decode_data_fountain,
    _HAS_PYFINITE,
)
from genecoder.bch_codec import (
    encode_data_bch,
    decode_data_bch,
    _HAS_BCHLIB,
)
from genecoder.raptorq_codec import (
    encode_data_raptorq,
    decode_data_raptorq,
    _HAS_RAPTORQ,
)


@pytest.mark.parametrize(
    "fec_name,encode_fn,decode_fn,available",
    [
        ("hamming_7_4", encode_data_with_hamming, decode_data_with_hamming, True),
        ("reed_solomon", encode_data_rs, decode_data_rs, _HAS_REEDSOLO),
        ("ldpc", encode_data_ldpc, decode_data_ldpc, _HAS_PYLDPC),
        ("fountain", encode_data_fountain, decode_data_fountain, _HAS_PYFINITE),
        ("bch", encode_data_bch, decode_data_bch, _HAS_BCHLIB),
        ("raptorq", encode_data_raptorq, decode_data_raptorq, _HAS_RAPTORQ),
    ],
    ids=[
        "hamming_7_4",
        "reed_solomon",
        "ldpc",
        "fountain",
        "bch",
        "raptorq",
    ],
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

    dna_chunks = list(
        stream_encode(chunks, encode_base4_direct, fec_encode=fec_enc)
    )

    def decode_direct(dna: str) -> bytes:
        return decode_base4_direct(dna)[0]

    def fec_dec(chunk: bytes, _info: object):
        info = infos.pop(0)
        return decode_fn(chunk, info)

    decoded_chunks = list(
        stream_decode(dna_chunks, decode_direct, fec_decode=fec_dec)
    )

    assert b"".join(decoded_chunks) == data