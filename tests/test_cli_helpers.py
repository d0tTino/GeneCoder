import argparse
from pathlib import Path
from genecoder.formats import to_fasta, from_fasta
from src.cli import (
    build_encoding_options,
    build_decoding_options,
    run_encoding_pipeline,
    run_decoding_pipeline,
)
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T


def test_run_encoding_and_decoding_pipeline(tmp_path: Path):
    data = b"CLI helper test"
    input_file = tmp_path / "input.bin"
    input_file.write_bytes(data)

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
    dna, header, *_ = run_encoding_pipeline(data, enc_opts, input_file.name)
    fasta = to_fasta(dna, header)
    fasta_file = tmp_path / "encoded.fasta"
    fasta_file.write_text(fasta)

    records = from_fasta(fasta)
    seq_header, seq = records[0]
    dec_args = argparse.Namespace(
        method="base4_direct",
        check_parity=False,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
    )
    dec_opts = build_decoding_options(dec_args)
    out_bytes = run_decoding_pipeline(seq, seq_header, dec_opts, input_file.name)
    assert out_bytes == data


def test_hamming_pipeline(tmp_path: Path):
    data = b"Hello"
    input_file = tmp_path / "in.bin"
    input_file.write_bytes(data)

    enc_args = argparse.Namespace(
        method="base4_direct",
        add_parity=True,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
        fec="hamming_7_4",
        gc_min=0.45,
        gc_max=0.55,
        max_homopolymer=3,
    )
    enc_opts = build_encoding_options(enc_args)
    dna, header, *_ = run_encoding_pipeline(data, enc_opts, input_file.name)
    assert "fec=hamming_7_4" in header
    dec_args = argparse.Namespace(
        method="base4_direct",
        check_parity=False,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
    )
    dec_opts = build_decoding_options(dec_args)
    out_bytes = run_decoding_pipeline(dna, header, dec_opts, input_file.name)
    assert out_bytes == data
