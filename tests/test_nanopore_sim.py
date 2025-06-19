import logging
import subprocess
import random
import pytest

from genecoder import nanopore_sim

ADAPTERS = {
    "d2sim": (nanopore_sim.simulate_d2sim, "d2sim"),
    "dnarsim": (nanopore_sim.simulate_dnarsim, "dnarsim"),
    "squigulator": (nanopore_sim.simulate_squigulator, "squigulator"),
}


@pytest.mark.parametrize("name", ADAPTERS.keys())
def test_adapters_run_external(monkeypatch, name):
    func, cmd = ADAPTERS[name]
    which_called = []
    run_called = []

    def fake_which(target):
        which_called.append(target)
        return "/usr/bin/" + target

    def fake_run_external(command, seq):
        run_called.append((command, seq))
        return "external"

    monkeypatch.setattr(nanopore_sim.shutil, "which", fake_which)
    monkeypatch.setattr(nanopore_sim, "_run_external", fake_run_external)

    result = func("ACGT")
    assert result == "external"
    assert which_called == [cmd]
    assert run_called == [(cmd, "ACGT")]


@pytest.mark.parametrize("name", ADAPTERS.keys())
def test_adapters_fall_back(monkeypatch, name):
    func, cmd = ADAPTERS[name]
    which_called = []
    errors_called = []

    monkeypatch.setattr(nanopore_sim.shutil, "which", lambda target: which_called.append(target) or None)
    monkeypatch.setattr(
        nanopore_sim,
        "simulate_errors",
        lambda seq, rate, rng=None: errors_called.append((seq, rate, rng)) or "fallback",
    )
    monkeypatch.setattr(nanopore_sim, "_run_external", lambda *_: "boom")

    result = func("ACGT", error_rate=0.1)
    assert result == "fallback"
    assert which_called == [cmd]
    assert errors_called == [("ACGT", 0.1, None)]


@pytest.mark.parametrize("name", ADAPTERS.keys())
def test_adapters_external_error(monkeypatch, caplog, name):
    func, cmd = ADAPTERS[name]
    which_called = []
    run_called = []
    errors_called = []

    monkeypatch.setattr(nanopore_sim.shutil, "which", lambda target: which_called.append(target) or "/usr/bin/" + target)

    def fake_run_external(command, seq):
        run_called.append((command, seq))
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(nanopore_sim, "_run_external", fake_run_external)
    monkeypatch.setattr(
        nanopore_sim,
        "simulate_errors",
        lambda s, r, rng=None: errors_called.append((s, r, rng)) or "fallback",
    )

    with caplog.at_level(logging.WARNING):
        result = func("ACGT", error_rate=0.2)

    assert result == "fallback"
    assert which_called == [cmd]
    assert run_called == [(cmd, "ACGT")]
    assert errors_called == [("ACGT", 0.2, None)]
    assert any("falling back" in rec.message for rec in caplog.records)


def test_simulate_reads_dispatch(monkeypatch):
    called = []
    def fake_adapter(seq: str, rate: float = 0.05, rng=None) -> str:
        called.append((seq, rate, rng))
        return "ok"

    monkeypatch.setitem(nanopore_sim.SIMULATOR_ADAPTERS, "dummy", fake_adapter)
    assert nanopore_sim.simulate_reads("AAAA", "dummy") == "ok"
    assert len(called) == 1
    assert called[0][0] == "AAAA"
    assert called[0][1] == 0.05
    assert isinstance(called[0][2], random.Random)


def test_simulate_reads_does_not_affect_global_rng(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "5")
    random.seed(123)
    random.random()
    # Reset and reproduce expected second value without calling simulate_reads
    random.seed(123)
    _ = random.random()
    expected_second = random.random()

    random.seed(123)
    _ = random.random()
    nanopore_sim.simulate_reads("AAAA", "none")
    after = random.random()

    assert after == expected_second
