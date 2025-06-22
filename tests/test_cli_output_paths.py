import argparse
import os
from pathlib import Path
import pytest

from genecoder.cli.encode import process_single_encode
from genecoder.cli.decode import process_single_decode
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T


def _encode_args() -> argparse.Namespace:
    return argparse.Namespace(
        method="base4_direct",
        add_parity=False,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
        fec=None,
        gc_min=0.45,
        gc_max=0.55,
        max_homopolymer=3,
        alphabet="base4",
        stream=False,
        capsule=None,
        export_csv=None,
    )


def _decode_args() -> argparse.Namespace:
    return argparse.Namespace(
        method="base4_direct",
        check_parity=False,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
        alphabet="base4",
        stream=False,
        simulate_errors=0.0,
        simulator="none",
    )


def test_process_single_encode_no_directory(tmp_path: Path) -> None:
    infile = tmp_path / "input.bin"
    infile.write_text("hello")
    args = _encode_args()
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        process_single_encode(str(infile), "out.fasta", args)
    finally:
        os.chdir(cwd)
    assert (tmp_path / "out.fasta").exists()


def test_process_single_decode_no_directory(tmp_path: Path) -> None:
    infile = tmp_path / "data.bin"
    infile.write_text("world")
    enc_args = _encode_args()
    fasta = tmp_path / "encoded.fasta"
    process_single_encode(str(infile), str(fasta), enc_args)

    dec_args = _decode_args()
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        process_single_decode(str(fasta), "decoded.bin", dec_args)
    finally:
        os.chdir(cwd)
    assert (tmp_path / "decoded.bin").read_text() == "world"


def test_process_single_decode_unknown_simulator(tmp_path: Path) -> None:
    infile = tmp_path / "data.bin"
    infile.write_text("abc")
    enc_args = _encode_args()
    fasta = tmp_path / "enc.fasta"
    process_single_encode(str(infile), str(fasta), enc_args)

    dec_args = _decode_args()
    dec_args.simulator = "bogus"
    with pytest.raises(SystemExit) as exc:
        process_single_decode(str(fasta), str(tmp_path / "out.bin"), dec_args)
    assert exc.value.code != 0

