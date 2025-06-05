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
