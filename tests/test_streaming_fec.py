import os
import pytest

from genecoder.streaming import stream_encode_file, stream_decode_file
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T
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
)
def test_stream_encode_decode_with_fec(tmp_path, fec_name, encode_fn, decode_fn, available):
    if not available:
        pytest.skip(f"{fec_name} not available")

    if fec_name == "fountain":
        pytest.importorskip("pyfinite")

    data = os.urandom(256)
    encoded_bytes, info = encode_fn(data)

    input_file = tmp_path / "in.bin"
    encoded_file = tmp_path / "encoded.fasta"
    decoded_file = tmp_path / "decoded.bin"

    input_file.write_bytes(encoded_bytes)

    header = f"method=base4_direct fec={fec_name}"
    stream_encode_file(
        str(input_file),
        str(encoded_file),
        header=header,
        add_parity=True,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
    )

    stream_decode_file(
        str(encoded_file),
        str(decoded_file),
        check_parity=True,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
    )

    decoded_fec_bytes = decoded_file.read_bytes()
    decoded_data, _ = decode_fn(decoded_fec_bytes, info)
    assert decoded_data == data


def test_decode_invalid_dna_length(tmp_path):
    data = b"hello"
    input_file = tmp_path / "in.bin"
    encoded_file = tmp_path / "encoded.fasta"
    input_file.write_bytes(data)
    header = "method=base4_direct"
    stream_encode_file(str(input_file), str(encoded_file), header=header)

    # Corrupt the FASTA by removing a nucleotide to break chunk alignment
    text = encoded_file.read_text().rstrip()[:-1]
    encoded_file.write_text(text)

    with pytest.raises(ValueError):
        stream_decode_file(str(encoded_file), str(tmp_path / "out.bin"))


@pytest.mark.parametrize(
    "decode_fn,broken_info",
    [
        (decode_data_with_hamming, -1),
        (decode_data_rs, 5),
        (decode_data_ldpc, {}),
        (decode_data_fountain, {}),
        (decode_data_bch, {}),
        (decode_data_raptorq, {}),
    ],
)
def test_fec_missing_metadata(decode_fn, broken_info):
    with pytest.raises(Exception):
        decode_fn(b"test", broken_info)
