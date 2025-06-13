import argparse
from src.cli import (
    build_encoding_options,
    build_decoding_options,
    run_encoding_pipeline,
    run_decoding_pipeline,
)

from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T

def test_encoding_decoding_triple_repeat(tmp_path):
    data = b"hello world"
    enc_args = argparse.Namespace(
        method="base4_direct",
        add_parity=False,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
        fec="triple_repeat",
        gc_min=0.45,
        gc_max=0.55,
        max_homopolymer=3,
    )
    enc_opts = build_encoding_options(enc_args)
    dna, header, raw_dna, *_ = run_encoding_pipeline(data, enc_opts, "in.bin")
    assert "fec=triple_repeat" in header
    assert len(dna) == len(raw_dna) * 3

    dec_args = argparse.Namespace(
        method="base4_direct",
        check_parity=False,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
    )
    dec_opts = build_decoding_options(dec_args)
    out_bytes = run_decoding_pipeline(dna, header, dec_opts, "in.bin")
    assert out_bytes == data


def test_run_encoding_unknown_fec_warning(capsys):
    data = b"abc"
    enc_args = argparse.Namespace(
        method="base4_direct",
        add_parity=False,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
        fec="bogus",
        gc_min=0.45,
        gc_max=0.55,
        max_homopolymer=3,
    )
    enc_opts = build_encoding_options(enc_args)
    dna, header, *_ = run_encoding_pipeline(data, enc_opts, "x.bin")
    captured = capsys.readouterr()
    assert "Unknown FEC method 'bogus'" in captured.err
    assert "fec=bogus" not in header
    assert dna


