import re
import pytest

from genecoder.app_helpers import EncodeOptions, perform_encoding, perform_decoding


def test_roundtrip_base4_direct_hamming():
    data = b"Hello GeneCoder"
    opts = EncodeOptions(
        method="Base-4 Direct",
        add_parity=True,
        k_value=7,
        fec_method="Hamming(7,4)",
    )
    enc = perform_encoding(data, opts)
    header_line = enc.fasta.splitlines()[0]
    assert "fec=hamming_7_4" in header_line
    assert any("Hamming(7,4) FEC applied." in m for m in enc.info_messages)
    assert any("Add Parity" in m for m in enc.info_messages)

    corrected = enc.fasta.replace("method=base_4_direct", "method=base4_direct")
    dec = perform_decoding(corrected)
    assert dec.decoded_bytes == data
    assert re.search(r"Hamming\(7,4\) FEC: \d+ corrected", dec.status_message)


def test_reed_solomon_roundtrip():
    data = b"RS GUI"
    opts = EncodeOptions(method="Base-4 Direct", fec_method="Reed-Solomon")
    enc = perform_encoding(data, opts)
    header = enc.fasta.splitlines()[0]
    assert "fec=reed_solomon" in header
    assert any("Reed-Solomon FEC applied." in m for m in enc.info_messages)

    corrected = enc.fasta.replace("method=base_4_direct", "method=base4_direct")
    dec = perform_decoding(corrected)
    assert dec.decoded_bytes == data
    assert "Reed-Solomon FEC" in dec.status_message


def test_triple_repeat_length_warning():
    data = b"ABC"
    opts = EncodeOptions(method="Base-4 Direct", fec_method="Triple-Repeat")
    enc = perform_encoding(data, opts)
    header = enc.fasta.splitlines()[0]
    seq = enc.fasta.splitlines()[1][:-1]  # break length multiple of 3
    modified = f">{header}\n{seq}\n"
    corrected = modified.replace("method=base_4_direct", "method=base4_direct")
    with pytest.raises(ValueError):
        perform_decoding(corrected)


def test_decoding_invalid_huffman_json():
    fasta = ">method=huffman input_file=x huffman_params={\"table\":{\"65\":\"0\"},\"padding\":0\nAAAA\n"
    with pytest.raises(ValueError):
        perform_decoding(fasta)


def test_decoding_missing_rs_nsym():
    data = b"DATA"
    opts = EncodeOptions(method="Base-4 Direct", fec_method="Reed-Solomon")
    enc = perform_encoding(data, opts)
    header = enc.fasta.splitlines()[0]
    header = re.sub(r"fec_nsym=\d+", "", header)
    header = header.replace("method=base_4_direct", "method=base4_direct")
    fasta = f">{header}\n{enc.fasta.splitlines()[1]}\n"
    result = perform_decoding(fasta)
    assert result.decoded_bytes != data
    assert "fec_nsym' missing" in result.status_message
