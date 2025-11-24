import random

from genecoder import illumina_sim
from genecoder.simulators.illumina.channel import IlluminaChannel
from genecoder.simulators.illumina.profiles import ILLUMINA_PROFILES


def _hamming(a: str, b: str) -> int:
    length = min(len(a), len(b))
    dist = sum(1 for i in range(length) if a[i] != b[i])
    return dist + abs(len(a) - len(b))


def test_coverage_reduces_errors() -> None:
    seq = "A" * 50
    rng1 = random.Random(0)
    out1 = illumina_sim.simulate(
        seq,
        substitution_rate=0.1,
        insertion_rate=0.001,
        deletion_rate=0.001,
        rng=rng1,
        coverage_depth=1,
    )
    rng2 = random.Random(0)
    out5 = illumina_sim.simulate(
        seq,
        substitution_rate=0.1,
        insertion_rate=0.001,
        deletion_rate=0.001,
        rng=rng2,
        coverage_depth=5,
    )
    assert _hamming(seq, out5) <= _hamming(seq, out1)


def test_quality_distribution_controls_errors() -> None:
    seq = "ACGTAC"
    rng1 = random.Random(0)
    out_none = illumina_sim.simulate(
        seq,
        substitution_rate=0.0,
        insertion_rate=0.0,
        deletion_rate=0.0,
        rng=rng1,
        coverage_depth=1,
        quality_distribution=[0.0],
    )
    rng2 = random.Random(0)
    out_all = illumina_sim.simulate(
        seq,
        substitution_rate=0.0,
        insertion_rate=0.0,
        deletion_rate=0.0,
        rng=rng2,
        coverage_depth=1,
        quality_distribution=[1.0],
    )
    assert out_none == seq
    assert _hamming(seq, out_all) == len(seq)


def test_illumina_profile_error_rates() -> None:
    sequence = "ACGT" * 250
    for name, params in ILLUMINA_PROFILES.items():
        channel = IlluminaChannel(profile=name)
        reads = int(max(1, channel.coverage)) * 500
        observation = channel.observe_error_rates(sequence, reads=reads, seed=2024)
        rates = observation.rates()
        for key in ("substitution_rate", "insertion_rate", "deletion_rate"):
            expected = float(params[key])
            tolerance = max(0.0001, expected * 0.5)
            assert abs(rates[key] - expected) <= tolerance

