import pytest

from genecoder.gc_constrained_encoder import (
    decode_gc_balanced,
    calculate_gc_content,
    get_max_homopolymer_length,
)
from genecoder.encoders import encode_base4_direct
from genecoder.constraint_fixer import fix


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
