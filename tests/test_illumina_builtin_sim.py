import random

from genecoder import illumina_sim
from genecoder.random_utils import reset_rng


def test_simulate_deterministic_with_rng():
    seq = "ACGTACGT"
    rng = random.Random(0)
    first = illumina_sim.simulate(seq, error_rate=0.1, rng=rng)
    rng = random.Random(0)
    second = illumina_sim.simulate(seq, error_rate=0.1, rng=rng)
    assert first == second


def test_channel_respects_seed(monkeypatch):
    seq = "ACGTACGT"
    monkeypatch.setenv("GENECODER_SIM_SEED", "7")
    reset_rng()
    ch = illumina_sim.Channel(error_rate=0.1)
    first = ch.simulate(seq)
    monkeypatch.setenv("GENECODER_SIM_SEED", "7")
    reset_rng()
    ch = illumina_sim.Channel(error_rate=0.1)
    second = ch.simulate(seq)
    assert first == second
