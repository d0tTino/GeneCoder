import random

from genecoder import illumina_sim


def _hamming(a: str, b: str) -> int:
    length = min(len(a), len(b))
    dist = sum(1 for i in range(length) if a[i] != b[i])
    return dist + abs(len(a) - len(b))


def test_coverage_reduces_errors() -> None:
    seq = "A" * 50
    rng1 = random.Random(0)
    out1 = illumina_sim.simulate(seq, error_rate=0.1, rng=rng1, coverage=1)
    rng2 = random.Random(0)
    out5 = illumina_sim.simulate(seq, error_rate=0.1, rng=rng2, coverage=5)
    assert _hamming(seq, out5) <= _hamming(seq, out1)


def test_quality_profile_position_specific() -> None:
    seq = "ACGTAC"
    rng = random.Random(0)
    out = illumina_sim.simulate(
        seq,
        error_rate=0.0,
        rng=rng,
        coverage=1,
        quality_profile=[0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
    )
    assert out[1] != seq[1]
    assert out[:1] + out[2:] == seq[:1] + seq[2:]

