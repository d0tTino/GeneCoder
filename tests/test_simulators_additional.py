import random
import pytest

from genecoder import nanopore_sim
from genecoder.simulators import simulate_reads
from genecoder.channel_sim import simulate_errors


def test_simulate_errors_preserves_global_rng():
    rng = random.Random(123)
    expected_first = rng.random()
    expected_second = rng.random()
    random.seed(123)
    before = random.random()
    simulate_errors("AAAA", 0.1)
    after = random.random()
    assert before == expected_first
    assert after == expected_second


@pytest.mark.parametrize("prob", [-0.1, 1.1])
def test_simulate_errors_invalid_probability(prob):
    with pytest.raises(ValueError):
        simulate_errors("A", prob)


def test_simulate_reads_fallback(monkeypatch):
    which_called = []
    errors_called = []

    monkeypatch.setattr(nanopore_sim.shutil, "which", lambda t: which_called.append(t) or None)
    monkeypatch.setattr(nanopore_sim, "_run_external", lambda *_: "boom")
    monkeypatch.setattr(
        nanopore_sim,
        "simulate_errors",
        lambda seq, rate, rng=None: errors_called.append((seq, rate, rng)) or "fallback",
    )

    result = simulate_reads("ACGT", "d2sim", error_rate=0.1)
    assert result == "fallback"
    assert which_called == ["d2sim"]
    assert errors_called and isinstance(errors_called[0][2], random.Random)
