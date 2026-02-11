import random

import pytest

from genecoder.constraint_fixer import (
    adjust_gc_balance,
    encode,
    fix_sequence,
    fix_sequence_with_report,
    limit_homopolymers,
)
from genecoder.gc_constrained_encoder import calculate_gc_content
from genecoder.random_utils import reset_rng
from genecoder.utils import get_max_homopolymer_length


def test_adjust_gc_balance_increases_gc():
    seq = "AAAAAA"
    fixed = adjust_gc_balance(seq, 0.4, 0.6, rng=random.Random(0))
    assert calculate_gc_content(fixed) >= 0.4


def test_adjust_gc_balance_long_sequence():
    seq = "AT" * 5000
    fixed = adjust_gc_balance(seq, 0.4, 0.6, rng=random.Random(0))
    assert 0.4 <= calculate_gc_content(fixed) <= 0.6
    assert len(fixed) == len(seq)


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


def test_fix_sequence_handles_long_input() -> None:
    seq = "A" * 1000
    fixed = fix_sequence(
        seq,
        target_gc_min=0.4,
        target_gc_max=0.6,
        max_homopolymer=4,
        rng=random.Random(0),
    )
    assert 0.4 <= calculate_gc_content(fixed) <= 0.6
    assert get_max_homopolymer_length(fixed) <= 4
    assert len(fixed) == len(seq)


def test_adjust_gc_balance_seed_reproducible(monkeypatch) -> None:
    monkeypatch.setenv("GENECODER_SIM_SEED", "123")
    seq = "AAAAAA"
    reset_rng()
    fixed1 = adjust_gc_balance(seq, 0.4, 0.6)
    reset_rng()
    fixed2 = adjust_gc_balance(seq, 0.4, 0.6)
    assert fixed1 == fixed2


def test_limit_homopolymers_seed_reproducible(monkeypatch) -> None:
    monkeypatch.setenv("GENECODER_SIM_SEED", "123")
    seq = "AAAAAA"
    reset_rng()
    fixed1 = limit_homopolymers(seq, 2)
    reset_rng()
    fixed2 = limit_homopolymers(seq, 2)
    assert fixed1 == fixed2


def test_fix_sequence_seed_reproducible(monkeypatch) -> None:
    monkeypatch.setenv("GENECODER_SIM_SEED", "123")
    seq = "A" * 12
    reset_rng()
    fixed1 = fix_sequence(
        seq,
        target_gc_min=0.4,
        target_gc_max=0.6,
        max_homopolymer=3,
    )
    reset_rng()
    fixed2 = fix_sequence(
        seq,
        target_gc_min=0.4,
        target_gc_max=0.6,
        max_homopolymer=3,
    )
    assert fixed1 == fixed2


def test_fix_sequence_invalid_parameters() -> None:
    with pytest.raises(ValueError):
        fix_sequence("AT", target_gc_min=0.6, target_gc_max=0.4, max_homopolymer=1)
    with pytest.raises(ValueError):
        fix_sequence("AT", target_gc_min=0.4, target_gc_max=0.6, max_homopolymer=0)



def test_encode_reports_repair_diff_metadata() -> None:
    seq = "A" * 12
    fixed, metrics = encode(
        seq,
        gc_min=0.4,
        gc_max=0.6,
        max_homopolymer=3,
        rng=random.Random(0),
    )
    assert fixed != seq
    repair = metrics.get("repair_report")
    assert isinstance(repair, dict)
    assert repair.get("strategy") == "stochastic"
    changes = repair.get("changes")
    assert isinstance(changes, list)
    assert changes


def test_fix_sequence_with_report_deterministic_strategy() -> None:
    fixed, report = fix_sequence_with_report(
        "AAAAAA",
        target_gc_min=0.4,
        target_gc_max=0.6,
        max_homopolymer=2,
        strategy="deterministic",
    )
    assert 0.4 <= calculate_gc_content(fixed) <= 0.6
    assert get_max_homopolymer_length(fixed) <= 2
    assert report["strategy"] == "deterministic"
