import argparse
import base64
import pytest

from genecoder.cli import (
    build_encoding_options,
    build_decoding_options,
    run_encoding_pipeline,
    run_decoding_pipeline,
)
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T
from genecoder import plugins


def _sample_dna(data: bytes) -> tuple[str, str]:
    plugins.load_plugins()
    enc_args = argparse.Namespace(
        method="base4_direct",
        add_parity=False,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
        fec=None,
        gc_min=0.45,
        gc_max=0.55,
        max_homopolymer=3,
    )
    enc_opts = build_encoding_options(enc_args)
    dna, header, *_ = run_encoding_pipeline(data, enc_opts, "in.bin")
    return dna, header


def _decoding_opts():
    plugins.load_plugins()
    dec_args = argparse.Namespace(
        method="base4_direct",
        check_parity=False,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
    )
    dec_opts = build_decoding_options(dec_args)
    return dec_opts


def test_run_decoding_invalid_fec_info_base64() -> None:
    dna, header = _sample_dna(b"abc")
    header += " fec=reed_solomon fec_info=abc"
    dec_opts = _decoding_opts()
    with pytest.raises(ValueError, match="Invalid 'fec_info'"):
        run_decoding_pipeline(dna, header, dec_opts, "in.bin")


def test_run_decoding_invalid_fec_info_json() -> None:
    dna, header = _sample_dna(b"abc")
    bad_json = base64.b64encode(b"not json").decode()
    header += f" fec=reed_solomon fec_info={bad_json}"
    dec_opts = _decoding_opts()
    with pytest.raises(ValueError, match="Invalid 'fec_info'"):
        run_decoding_pipeline(dna, header, dec_opts, "in.bin")
