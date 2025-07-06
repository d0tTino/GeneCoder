import random

from genecoder.constraint_fixer import adjust_gc_balance, limit_homopolymers, fix_sequence
from genecoder.gc_constrained_encoder import calculate_gc_content
from genecoder.utils import get_max_homopolymer_length


def test_adjust_gc_balance_increases_gc():
    seq = "AAAAAA"
    fixed = adjust_gc_balance(seq, 0.4, 0.6, rng=random.Random(0))
    assert calculate_gc_content(fixed) >= 0.4


def test_limit_homopolymers_breaks_runs():
    seq = "AAAAAA"
    fixed = limit_homopolymers(seq, 2, rng=random.Random(0))
    assert get_max_homopolymer_length(fixed) <= 2


def test_fix_sequence_handles_empty():
    assert fix_sequence("", target_gc_min=0.4, target_gc_max=0.6, max_homopolymer=3) == ""


def test_fix_sequence_no_change_needed():
    seq = "ATGCATGC"
    fixed = fix_sequence(seq, target_gc_min=0.4, target_gc_max=0.6, max_homopolymer=3)
    assert fixed == seq


def test_fix_sequence_enforces_gc_and_homopolymer_limits_low_gc() -> None:
    seq = "A" * 12
    fixed = fix_sequence(
        seq,
        target_gc_min=0.4,
        target_gc_max=0.6,
        max_homopolymer=3,
        rng=random.Random(0),
    )
    assert 0.4 <= calculate_gc_content(fixed) <= 0.6
    assert get_max_homopolymer_length(fixed) <= 3
    assert len(fixed) == len(seq)


def test_fix_sequence_enforces_gc_and_homopolymer_limits_high_gc() -> None:
    seq = "G" * 10
    fixed = fix_sequence(
        seq,
        target_gc_min=0.4,
        target_gc_max=0.6,
        max_homopolymer=2,
        rng=random.Random(0),
    )
    assert 0.4 <= calculate_gc_content(fixed) <= 0.6
    assert get_max_homopolymer_length(fixed) <= 2
    assert len(fixed) == len(seq)

