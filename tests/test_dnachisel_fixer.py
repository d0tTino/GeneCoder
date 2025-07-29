import pytest

pytest.importorskip("dnachisel")

from genecoder.dnachisel_fixer import fix_sequence_dnachisel
from genecoder.encoders import calculate_gc_content
from genecoder.utils import get_max_homopolymer_length


def test_dnachisel_fix_low_gc() -> None:
    seq = "A" * 20
    fixed = fix_sequence_dnachisel(seq, gc_min=0.4, gc_max=0.6, max_homopolymer=3)
    assert 0.4 <= calculate_gc_content(fixed) <= 0.6
    assert get_max_homopolymer_length(fixed) <= 3
    assert len(fixed) == len(seq)


def test_dnachisel_fix_high_gc() -> None:
    seq = "G" * 20
    fixed = fix_sequence_dnachisel(seq, gc_min=0.4, gc_max=0.6, max_homopolymer=2)
    assert 0.4 <= calculate_gc_content(fixed) <= 0.6
    assert get_max_homopolymer_length(fixed) <= 2
    assert len(fixed) == len(seq)
