import pytest

from genecoder.gc_constrained_encoder import (
    decode_gc_balanced,
    calculate_gc_content,
    get_max_homopolymer_length,
)
from genecoder.encoders import encode_base4_direct


@pytest.mark.parametrize("which", ["gc", "homopolymer"])
def test_decode_gc_balanced_constraint_failures(which):
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
