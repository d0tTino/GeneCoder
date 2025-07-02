import logging
import random
import subprocess
import pytest

from genecoder import nanopore_sim
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.simulators import simulate_reads

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
    expected = ([cmd, "-e", "0.05"], "ACGT")
    assert run_called == [expected]


def test_d2sim_extra_options(monkeypatch):
    which_called = []
    run_called = []

    monkeypatch.setattr(nanopore_sim.shutil, "which", lambda t: which_called.append(t) or "/usr/bin/" + t)
    monkeypatch.setattr(
        nanopore_sim,
        "_run_external",
        lambda cmd, seq: run_called.append((cmd, seq)) or "ok",
    )
    monkeypatch.setenv("GENECODER_D2SIM_OPTIONS", "--foo bar")

    result = nanopore_sim.simulate_d2sim("ACGT", error_rate=0.1)
    assert result == "ok"
    assert run_called == [(["d2sim", "-e", "0.1", "--foo", "bar"], "ACGT")]


def test_parse_options_env(monkeypatch):
    monkeypatch.setenv("GENECODER_D2SIM_OPTIONS", "--alpha beta")
    assert nanopore_sim._parse_env_options("d2sim") == ["--alpha", "beta"]


def test_parse_options_invalid(monkeypatch, caplog):
    monkeypatch.setenv("GENECODER_D2SIM_OPTIONS", '"unclosed')
    with caplog.at_level(logging.WARNING):
        opts = nanopore_sim._parse_env_options("d2sim")
    assert opts == []
    assert any("Invalid" in r.message for r in caplog.records)


def test_parse_options_unsafe(monkeypatch):
    monkeypatch.setenv("GENECODER_D2SIM_OPTIONS", "foo;bar")
    with pytest.raises(ValueError):
        nanopore_sim._parse_env_options("d2sim")


@pytest.mark.parametrize("name", ADAPTERS.keys())
def test_adapters_invalid_env_options(monkeypatch, name):
    func, cmd = ADAPTERS[name]
    monkeypatch.setattr(nanopore_sim.shutil, "which", lambda t: "/usr/bin/" + t)
    run_called = []
    monkeypatch.setattr(
        nanopore_sim,
        "_run_external",
        lambda *_: run_called.append(True) or "ok",
    )
    monkeypatch.setenv(f"GENECODER_{cmd.upper()}_OPTIONS", "foo;bar")
    with pytest.raises(ValueError):
        func("ACGT")
    assert not run_called


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
    expected = ([cmd, "-e", "0.2"], "ACGT")
    assert run_called == [expected]
    assert errors_called and isinstance(errors_called[0][2], random.Random)
    assert any("falling back" in rec.message for rec in caplog.records)


@pytest.mark.parametrize("name", ADAPTERS.keys())
def test_adapters_invalid_output(monkeypatch, caplog, name):
    func, cmd = ADAPTERS[name]
    which_called = []
    errors_called = []

    monkeypatch.setattr(nanopore_sim.shutil, "which", lambda t: which_called.append(t) or "/usr/bin/" + t)
    monkeypatch.setattr(
        nanopore_sim,
        "_run_external",
        lambda *_: (_ for _ in ()).throw(RuntimeError("bad output")),
    )
    monkeypatch.setattr(
        nanopore_sim,
        "simulate_errors",
        lambda s, r, rng=None: errors_called.append((s, r, rng)) or "fallback",
    )

    with caplog.at_level(logging.WARNING):
        result = func("ACGT")

    assert result == "fallback"
    assert which_called == [cmd]
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
    class DummyChannel(nanopore_sim.Channel):
        def __init__(self):
            super().__init__("dummy", 0.05)

        def simulate(self, sequence: str) -> str:
            called.append((sequence, self.error_rate))
            return "ok"

    monkeypatch.setitem(SIMULATOR_REGISTRY, "dummy", DummyChannel())
    assert simulate_reads("AAAA", "dummy") == "ok"
    assert called == [("AAAA", 0.05)]


def test_simulate_reads_preserves_global_rng(monkeypatch):
    class DummyChannel(nanopore_sim.Channel):
        def __init__(self):
            super().__init__("dummy")

        def simulate(self, sequence: str) -> str:
            return sequence

    monkeypatch.setitem(SIMULATOR_REGISTRY, "dummy", DummyChannel())

    rng = random.Random(123)
    expected_first = rng.random()
    expected_second = rng.random()
    random.seed(123)
    before = random.random()
    simulate_reads("ACGT", "dummy")
    after = random.random()
    assert before == expected_first
    assert after == expected_second


def test_simulate_reads_unknown_simulator():
    with pytest.raises(ValueError, match="Unknown simulator"):
        simulate_reads("ACGT", "bogus")


def test_register_returns_channels():
    from genecoder.channels.base import BaseChannel

    registry: dict[str, BaseChannel] = {}

    nanopore_sim.register(lambda name, chan: registry.setdefault(name, chan))

    assert registry
    assert all(isinstance(chan, BaseChannel) for chan in registry.values())


def test_simulate_reads_wrapper_deprecated(monkeypatch):
    called = []

    def fake_sim(seq: str, sim: str, error_rate: float = 0.05) -> str:
        called.append((seq, sim, error_rate))
        return "wrapped"

    monkeypatch.setattr(
        "genecoder.simulators.simulate_reads",
        fake_sim,
    )

    with pytest.deprecated_call():
        result = nanopore_sim.simulate_reads("ACGT", "none", error_rate=0.2)

    assert result == "wrapped"
    assert called == [("ACGT", "none", 0.2)]
