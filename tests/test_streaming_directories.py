import os
from genecoder.streaming import stream_encode_file, stream_decode_file


def test_stream_encode_file_creates_directory(tmp_path):
    data = os.urandom(128)
    input_file = tmp_path / "in.bin"
    input_file.write_bytes(data)
    output_file = tmp_path / "non" / "existent" / "out.fasta"
    header = "method=base4_direct input_file=in.bin"
    stream_encode_file(str(input_file), str(output_file), header=header)
    assert output_file.exists()


def test_stream_decode_file_creates_directory(tmp_path):
    data = os.urandom(128)
    input_file = tmp_path / "in.bin"
    encoded_file = tmp_path / "encoded.fasta"
    input_file.write_bytes(data)
    stream_encode_file(str(input_file), str(encoded_file), header="hdr")
    output_file = tmp_path / "dec" / "dir" / "decoded.bin"
    stream_decode_file(str(encoded_file), str(output_file))
    assert output_file.exists()
    assert output_file.read_bytes() == data
