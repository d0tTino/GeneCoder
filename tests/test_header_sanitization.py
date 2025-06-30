import argparse
from genecoder.cli.encode import run_encoding_pipeline, build_encoding_options
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T


def test_header_no_backslashes(tmp_path):
    data = b"x" * 10
    input_path = tmp_path / "subdir" / "in.bin"
    input_path.parent.mkdir()
    input_path.write_bytes(data)

    args = argparse.Namespace(
        method="base4_direct",
        add_parity=False,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
        fec=None,
        gc_min=0.45,
        gc_max=0.55,
        max_homopolymer=3,
        alphabet="base4",
    )
    opts = build_encoding_options(args)
    dna, header, *_ = run_encoding_pipeline(data, opts, "foo\\bar\\in.bin")
    assert "\\" not in header
    assert "input_file=in.bin" in header

