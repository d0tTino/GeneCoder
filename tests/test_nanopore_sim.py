import logging
import random
import subprocess
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
    expected = ([cmd, "-e", "0.05"], "ACGT") if cmd == "d2sim" else ([cmd], "ACGT")
    assert run_called == [expected]


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
    assert errors_called and isinstance(errors_called[0][2], random.Random)


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
    expected = ([cmd, "-e", "0.2"], "ACGT") if cmd == "d2sim" else ([cmd], "ACGT")
    assert run_called == [expected]
    assert errors_called and isinstance(errors_called[0][2], random.Random)
    assert any("falling back" in rec.message for rec in caplog.records)


@pytest.mark.parametrize("name", ADAPTERS.keys())
def test_adapters_command_not_found_warning(monkeypatch, caplog, name):
    func, cmd = ADAPTERS[name]
    errors_called = []

    monkeypatch.setattr(nanopore_sim.shutil, "which", lambda target: None)

    def boom(*_):
        raise AssertionError("_run_external should not be called")

    monkeypatch.setattr(nanopore_sim, "_run_external", boom)
    monkeypatch.setattr(
        nanopore_sim,
        "simulate_errors",
        lambda seq, rate, rng=None: errors_called.append((seq, rate, rng))
        or "fallback",
    )

    with caplog.at_level(logging.WARNING):
        result = func("ACGT")

    assert result == "fallback"
    assert errors_called and isinstance(errors_called[0][2], random.Random)
    assert any(
        rec.levelno == logging.WARNING and "not found" in rec.message
        for rec in caplog.records
    )


def test_simulate_reads_dispatch(monkeypatch):
    called = []
    def fake_adapter(seq: str, rate: float = 0.05, rng=None) -> str:
        called.append((seq, rate, isinstance(rng, random.Random)))

        return "ok"

    monkeypatch.setitem(nanopore_sim.SIMULATOR_ADAPTERS, "dummy", fake_adapter)
    assert nanopore_sim.simulate_reads("AAAA", "dummy") == "ok"
    assert called == [("AAAA", 0.05, True)]


def test_simulate_reads_preserves_global_rng(monkeypatch):
    def fake_adapter(seq: str, rate: float = 0.05, rng=None) -> str:
        return seq

    monkeypatch.setitem(nanopore_sim.SIMULATOR_ADAPTERS, "dummy", fake_adapter)

    rng = random.Random(123)
    expected_first = rng.random()
    expected_second = rng.random()
    random.seed(123)
    before = random.random()
    nanopore_sim.simulate_reads("ACGT", "dummy")
    after = random.random()
    assert before == expected_first
    assert after == expected_second


def test_simulate_reads_unknown_simulator():
    with pytest.raises(ValueError, match="Unknown simulator"):
        nanopore_sim.simulate_reads("ACGT", "bogus")


def test_register_returns_channels():
    from genecoder.channels.base import BaseChannel

    registry: dict[str, BaseChannel] = {}

    nanopore_sim.register(lambda name, chan: registry.setdefault(name, chan))

    assert registry
    assert all(isinstance(chan, BaseChannel) for chan in registry.values())
