import os
from genecoder.stream_pipeline import stream_encode, stream_decode
from genecoder.encoders import encode_base4_direct, decode_base4_direct
from genecoder.hamming_codec import encode_data_with_hamming, decode_data_with_hamming


def test_stream_pipeline_roundtrip_with_fec():
    chunks = [os.urandom(32) for _ in range(4)]
    encoded = list(
        stream_encode(chunks, encode_base4_direct, fec_encode=encode_data_with_hamming)
    )
    decoded_iter = stream_decode(
        encoded,
        lambda dna: decode_base4_direct(dna)[0],
        fec_decode=decode_data_with_hamming,
    )
    result = b"".join(decoded_iter)
    assert result == b"".join(chunks)

