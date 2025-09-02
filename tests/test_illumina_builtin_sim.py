import random

from genecoder import illumina_sim
from genecoder.random_utils import reset_rng


def test_simulate_deterministic_with_rng():
    seq = "ACGTACGT"
    rng = random.Random(0)
    first = illumina_sim.simulate(
        seq,
        substitution_rate=0.1,
        insertion_rate=0.001,
        deletion_rate=0.001,
        rng=rng,
    )
    rng = random.Random(0)
    second = illumina_sim.simulate(
        seq,
        substitution_rate=0.1,
        insertion_rate=0.001,
        deletion_rate=0.001,
        rng=rng,
    )
    assert first == second


def test_channel_respects_seed(monkeypatch):
    seq = "ACGTACGT"
    monkeypatch.setenv("GENECODER_SIM_SEED", "7")
    reset_rng()
    ch = illumina_sim.Channel(
        substitution_rate=0.1, insertion_rate=0.001, deletion_rate=0.001
    )
    first = ch.simulate(seq)
    monkeypatch.setenv("GENECODER_SIM_SEED", "7")
    reset_rng()
    ch = illumina_sim.Channel(
        substitution_rate=0.1, insertion_rate=0.001, deletion_rate=0.001
    )
    second = ch.simulate(seq)
    assert first == second


def test_coverage_influences_read_count(monkeypatch):
    seq = "ACGT"
    calls: list[int] = []

    def fake_mutate(*args, **kwargs) -> str:
        calls.append(1)
        return args[0]

    monkeypatch.setattr(illumina_sim, "_mutate_read", fake_mutate)

    rng = random.Random(0)
    out = illumina_sim.simulate(
        seq,
        substitution_rate=0.0,
        insertion_rate=0.0,
        deletion_rate=0.0,
        rng=rng,
        coverage_depth=5.0,
    )
    expected = illumina_sim._poisson(5.0, random.Random(0))
    assert len(calls) == expected
    assert out == seq

    calls.clear()
    rng = random.Random(0)
    out = illumina_sim.simulate(
        seq,
        substitution_rate=0.0,
        insertion_rate=0.0,
        deletion_rate=0.0,
        rng=rng,
        coverage_depth=0.1,
    )
    assert out == ""
    assert len(calls) == 0
