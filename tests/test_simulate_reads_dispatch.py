import random
import pytest

from genecoder import nanopore_sim
from genecoder.simulators import simulate_reads, SIMULATOR_REGISTRY


@pytest.mark.parametrize("name", ["d2sim", "dnarsim", "squigulator"])
def test_simulate_reads_calls_adapter(monkeypatch, name):
    which_called = []
    run_called = []

    def fake_which(target):
        which_called.append(target)
        return "/usr/bin/" + target

    def fake_run_external(cmd, seq):
        run_called.append((cmd, seq))
        return "external"

    monkeypatch.setattr(nanopore_sim.shutil, "which", fake_which)
    monkeypatch.setattr(nanopore_sim, "_run_external", fake_run_external)
    monkeypatch.setitem(SIMULATOR_REGISTRY, name, nanopore_sim.Channel(name))

    result = simulate_reads("ACGT", name)
    assert result == "external"
    assert which_called == [name]
    expected = ([name, "-e", "0.05"], "ACGT")
    assert run_called == [expected]



@pytest.mark.parametrize("name", ["d2sim", "dnarsim", "squigulator"])
def test_simulate_reads_adapter_fallback(monkeypatch, name):
    which_called = []
    errors_called = []

    monkeypatch.setattr(nanopore_sim.shutil, "which", lambda t: which_called.append(t) or None)
    monkeypatch.setattr(
        nanopore_sim,
        "simulate_errors",
        lambda seq, rate, rng=None: errors_called.append((seq, rate, rng)) or "fallback",
    )
    monkeypatch.setattr(nanopore_sim, "_run_external", lambda *_: "boom")
    monkeypatch.setitem(SIMULATOR_REGISTRY, name, nanopore_sim.Channel(name))

    result = simulate_reads("ACGT", name, error_rate=0.1)
    assert result == "fallback"
    assert which_called == [name]
    assert errors_called and isinstance(errors_called[0][2], random.Random)
