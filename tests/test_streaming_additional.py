import os
import pytest
from genecoder.streaming import stream_encode_file, stream_decode_file


def test_stream_encode_line_width(tmp_path):
    data = os.urandom(300)
    input_file = tmp_path / "in.bin"
    output_file = tmp_path / "out.fasta"
    input_file.write_bytes(data)

    header = "method=base4_direct input_file=in.bin"
    total_len = stream_encode_file(str(input_file), str(output_file), header=header, chunk_size=50)
    lines = output_file.read_text().splitlines()
    assert lines[0] == f">{header}"
    dna = "".join(lines[1:])
    assert len(dna) == total_len
    for line in lines[1:]:
        assert len(line) <= 80


def test_stream_decode_invalid_header(tmp_path):
    bad_file = tmp_path / "bad.fasta"
    bad_file.write_text("invalid\nACGT")
    out_file = tmp_path / "out.bin"
    with pytest.raises(ValueError):
        stream_decode_file(str(bad_file), str(out_file))

