import random
from genecoder.error_simulation import introduce_errors


def test_deterministic_substitutions():
    rng = random.Random(42)
    result = introduce_errors(
        "AAAA",
        substitution_prob=1.0,
        insertion_prob=0.0,
        deletion_prob=0.0,
        rng=rng,
    )
    assert result == "CGTG"


def test_deterministic_insertions():
    rng = random.Random(0)
    result = introduce_errors(
        "AT",
        substitution_prob=0.0,
        insertion_prob=1.0,
        deletion_prob=0.0,
        rng=rng,
    )
    assert result == "ACTC"


def test_deterministic_deletions():
    rng = random.Random(1)
    result = introduce_errors(
        "ATGC",
        substitution_prob=0.0,
        insertion_prob=0.0,
        deletion_prob=0.5,
        rng=rng,
    )
    assert result == "T"


def test_apply_functions_and_edge_cases():
    rng = random.Random(123)
    from genecoder.error_simulation import apply_substitutions, apply_insertions, apply_deletions

    # apply_substitutions with probability 0 should return the original sequence
    assert apply_substitutions("ATGC", prob=0.0, rng=rng) == "ATGC"

    # apply_insertions with probability 0 should return the original sequence
    assert apply_insertions("ATGC", prob=0.0, rng=rng) == "ATGC"

    # apply_deletions with probability 1.0 removes all characters
    assert apply_deletions("ATGC", prob=1.0, rng=rng) == ""


def test_introduce_errors_combined_operations():
    rng = random.Random(1)
    result = introduce_errors(
        "AT",
        substitution_prob=0.5,
        insertion_prob=0.5,
        deletion_prob=0.5,
        rng=rng,
    )
    assert result == "TG"


def test_introduce_errors_empty_sequence():
    assert introduce_errors("", substitution_prob=1.0, insertion_prob=1.0, deletion_prob=1.0, rng=random.Random(0)) == ""
