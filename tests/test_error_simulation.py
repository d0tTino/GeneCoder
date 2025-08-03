import random
import pytest
from genecoder.error_simulation import simulate_errors


def test_deterministic_substitutions():
    rng = random.Random(42)
    result = simulate_errors(
        "AAAA",
        substitution_prob=1.0,
        insertion_prob=0.0,
        deletion_prob=0.0,
        rng=rng,
    )
    assert result == "CGTG"


def test_deterministic_insertions():
    rng = random.Random(0)
    result = simulate_errors(
        "AT",
        substitution_prob=0.0,
        insertion_prob=1.0,
        deletion_prob=0.0,
        rng=rng,
    )
    assert result == "ACTC"


def test_deterministic_deletions():
    rng = random.Random(1)
    result = simulate_errors(
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


def test_simulate_errors_combined_operations():
    rng = random.Random(1)
    result = simulate_errors(
        "AT",
        substitution_prob=0.3,
        insertion_prob=0.3,
        deletion_prob=0.3,
        rng=rng,
    )
    assert result == "TG"


def test_simulate_errors_empty_sequence():
    assert (
        simulate_errors(
            "",
            substitution_prob=1.0,
            insertion_prob=0.0,
            deletion_prob=0.0,
            rng=random.Random(0),
        )
        == ""
    )


def test_simulate_errors_rate_approximation():
    """Verify that observed error rates roughly match the configured probabilities."""
    seq = "ACGT" * 250  # length 1000

    rng = random.Random(0)
    mutated = simulate_errors(seq, substitution_prob=0.1, rng=rng)
    subs = sum(1 for a, b in zip(seq, mutated) if a != b)
    assert abs(subs / len(seq) - 0.1) < 0.03

    rng = random.Random(0)
    mutated = simulate_errors(seq, insertion_prob=0.05, rng=rng)
    ins = len(mutated) - len(seq)
    assert abs(ins / len(seq) - 0.05) < 0.03

    rng = random.Random(0)
    mutated = simulate_errors(seq, deletion_prob=0.02, rng=rng)
    dels = len(seq) - len(mutated)
    assert abs(dels / len(seq) - 0.02) < 0.03


@pytest.mark.parametrize(
    "kw,value",
    [
        ("substitution_prob", -0.1),
        ("substitution_prob", 1.1),
        ("insertion_prob", -0.1),
        ("insertion_prob", 1.1),
        ("deletion_prob", -0.1),
        ("deletion_prob", 1.1),
    ],
)
def test_simulate_errors_invalid_probabilities(kw: str, value: float) -> None:
    kwargs = {kw: value, "rng": random.Random(0)}
    with pytest.raises(ValueError):
        simulate_errors("A", **kwargs)


def test_simulate_errors_probability_sum_exceeds_one() -> None:
    with pytest.raises(ValueError):
        simulate_errors(
            "A",
            substitution_prob=0.6,
            insertion_prob=0.3,
            deletion_prob=0.2,
            rng=random.Random(0),
        )
