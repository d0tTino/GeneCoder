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


def test_gc_balanced_roundtrip_with_parity():
    data = b"GC BAL"
    opts = EncodeOptions(
        method="GC-Balanced",
        add_parity=True,
        k_value=5,
        gc_min=0.3,
        gc_max=0.7,
        max_homopolymer=3,
    )
    enc = perform_encoding(data, opts)
    header = enc.fasta.splitlines()[0]
    assert "gc_min=" in header and "max_homopolymer=" in header
    # parity header fields should not appear when method is GC-Balanced
    assert "parity_k=" not in header
    dec = perform_decoding(enc.fasta)
    assert dec.decoded_bytes == data


def test_huffman_rs_parity_ignored():
    data = b"HF RS"
    opts = EncodeOptions(method="Huffman", add_parity=True, fec_method="Reed-Solomon", k_value=4)
    enc = perform_encoding(data, opts)
    header = enc.fasta.splitlines()[0]
    assert "fec=reed_solomon" in header
    assert "parity_k=" not in header
    assert any("Add Parity" in msg for msg in enc.info_messages)
    fasta = enc.fasta.replace("method=huffman", "method=huffman")
    dec = perform_decoding(fasta)
    assert dec.decoded_bytes == data
    assert dec.fec_info and "Reed-Solomon FEC" in dec.fec_info


def test_parity_error_detection():
    data = b"ERRCHK"
    opts = EncodeOptions(method="Base-4 Direct", add_parity=True, k_value=4)
    enc = perform_encoding(data, opts)
    lines = enc.fasta.splitlines()
    header = lines[0].replace("method=base_4_direct", "method=base4_direct")
    seq = list(lines[1])
    # flip first parity nucleotide (position k_value)
    parity_idx = 4
    seq[parity_idx] = "A" if seq[parity_idx] != "A" else "T"
    mutated = "".join(seq)
    fasta = f">{header}\n{mutated}\n"
    dec = perform_decoding(fasta)
    assert dec.decoded_bytes == data
    assert "Parity error(s)" in dec.status_message


def test_hamming_missing_padding_bits():
    data = b"PADMISS"
    opts = EncodeOptions(method="Base-4 Direct", fec_method="Hamming(7,4)")
    enc = perform_encoding(data, opts)
    header = enc.fasta.splitlines()[0]
    header = re.sub(r"fec_padding_bits=\d+", "", header)
    header = header.replace("method=base_4_direct", "method=base4_direct")
    fasta = f">{header}\n{enc.fasta.splitlines()[1]}\n"
    result = perform_decoding(fasta)
    assert "fec_padding_bits' missing" in result.status_message


def test_decoding_no_fasta_records():
    with pytest.raises(ValueError, match="No valid FASTA records found"):
        perform_decoding("")
