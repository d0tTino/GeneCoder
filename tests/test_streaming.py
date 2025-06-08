import os

from genecoder.streaming import stream_encode_file, stream_decode_file, encode_base4_direct, decode_base4_direct


def test_stream_round_trip(tmp_path, monkeypatch):
    data = os.urandom(1_500_000)
    input_file = tmp_path / "input.bin"
    encoded_file = tmp_path / "encoded.fasta"
    decoded_file = tmp_path / "decoded.bin"
    input_file.write_bytes(data)

    enc_calls = []
    orig_encode = encode_base4_direct

    def mock_encode(*args, **kwargs):
        enc_calls.append(kwargs.get("stream"))
        return orig_encode(*args, **kwargs)

    monkeypatch.setattr("genecoder.streaming.encode_base4_direct", mock_encode)

    header = "method=base4_direct input_file=test.bin"
    stream_encode_file(str(input_file), str(encoded_file), header=header)
    assert True in enc_calls

    dec_calls = []
    orig_decode = decode_base4_direct

    def mock_decode(*args, **kwargs):
        dec_calls.append(kwargs.get("stream"))
        return orig_decode(*args, **kwargs)

    monkeypatch.setattr("genecoder.streaming.decode_base4_direct", mock_decode)

    stream_decode_file(str(encoded_file), str(decoded_file))
    assert True in dec_calls

    assert decoded_file.read_bytes() == data
