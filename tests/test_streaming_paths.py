from genecoder.encoders import decode_base4_direct, encode_base4_direct


def test_encode_decode_stream_roundtrip() -> None:
    chunks = [b"hello", b"world"]
    encoded_iter = encode_base4_direct(chunks, stream=True)
    dna_chunks = list(encoded_iter)
    decoded_iter = decode_base4_direct(dna_chunks, stream=True)
    decoded = b"".join(part for part, _ in decoded_iter)
    assert decoded == b"helloworld"


def test_encode_stream_single_bytes() -> None:
    data = b"abc"
    encoded_iter = encode_base4_direct(data, stream=True)
    assert list(encoded_iter) == [encode_base4_direct(data)]


def test_decode_stream_single_string() -> None:
    dna = encode_base4_direct(b"xy")
    decoded_iter = decode_base4_direct(dna, stream=True)
    result = b"".join(part for part, _ in decoded_iter)
    assert result == b"xy"
