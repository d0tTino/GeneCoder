import pytest

from genecoder.gc_constrained_encoder import (
    decode_gc_balanced,
    calculate_gc_content,
    get_max_homopolymer_length,
)
from genecoder.encoders import encode_base4_direct
from genecoder.constraint_fixer import fix
from genecoder.cli.encode import process_single_encode
from genecoder.formats import from_fasta
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T
import argparse
import os


@pytest.mark.parametrize("which", ["gc", "homopolymer"])
def test_decode_gc_balanced_constraint_failures(which) -> None:
    data = b"edge"
    payload = encode_base4_direct(data)
    dna = "0" + payload
    gc = calculate_gc_content(payload)
    hp = get_max_homopolymer_length(payload)

    if which == "gc":
        with pytest.raises(ValueError, match="GC content"):
            decode_gc_balanced(dna, expected_gc_min=gc + 0.1)
    else:
        with pytest.raises(ValueError, match="homopolymer"):
            decode_gc_balanced(dna, expected_max_homopolymer=hp - 1)


@pytest.mark.parametrize("which", ["gc", "homopolymer"])
def test_auto_fix_permits_decode(which) -> None:
    data = b"edge"
    payload = encode_base4_direct(data)
    gc = calculate_gc_content(payload)
    hp = get_max_homopolymer_length(payload)

    if which == "gc":
        fixed_payload = fix(
            payload,
            gc_min=gc + 0.1,
            gc_max=1.0,
            max_homopolymer=hp,
        )
        decode_gc_balanced("0" + fixed_payload, expected_gc_min=gc + 0.1)
    else:
        fixed_payload = fix(
            payload,
            gc_min=0.0,
            gc_max=1.0,
            max_homopolymer=hp - 1,
        )
        decode_gc_balanced("0" + fixed_payload, expected_max_homopolymer=hp - 1)


@pytest.mark.parametrize("which", ["gc", "homopolymer"])
def test_cli_auto_fix_flag(tmp_path, which) -> None:
    data = b"edge"
    input_path = tmp_path / "in.bin"
    output_path = tmp_path / "out.fasta"
    input_path.write_bytes(data)

    payload = encode_base4_direct(data)
    gc = calculate_gc_content(payload)
    hp = get_max_homopolymer_length(payload)

    args = argparse.Namespace(
        stream=False,
        method="base4_direct",
        fec=None,
        chunk_size=0,
        resume=False,
        add_parity=False,
        k_value=0,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
        alphabet="base4",
        gc_min=gc + 0.1 if which == "gc" else 0.0,
        gc_max=1.0,
        max_homopolymer=hp if which == "gc" else hp - 1,
        auto_fix=True,
        fix_chisel=False,
        encrypt=False,
        key=None,
        checksum=False,
        mirror=False,
        capsule=None,
        file_type=None,
        output_dir=None,
        output_file=None,
        auto_ext=False,
        seed=None,
    )

    process_single_encode(str(input_path), str(output_path), args)
    fasta = output_path.read_text(encoding="utf-8")
    records = from_fasta(fasta)
    dna_sequence = records[0][1]
    os.remove(output_path)

    if which == "gc":
        decode_gc_balanced("0" + dna_sequence, expected_gc_min=gc + 0.1)
    else:
        decode_gc_balanced("0" + dna_sequence, expected_max_homopolymer=hp - 1)
