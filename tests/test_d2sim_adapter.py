import logging
import random
import subprocess

from genecoder import d2sim_adapter, nanopore_sim



def test_run_external(monkeypatch):
    which_called = []
    run_called = []

    def fake_which(target):
        which_called.append(target)
        return "/usr/bin/" + target

    def fake_run(command, seq):
        run_called.append((command, seq))
        return "external"

    monkeypatch.setattr(nanopore_sim.shutil, "which", fake_which)
    monkeypatch.setattr(nanopore_sim, "_run_external", fake_run)

    result = d2sim_adapter.simulate_d2sim("ACGT")
    assert result == "external"
    assert which_called == ["d2sim"]
    assert run_called == [(["d2sim", "-e", "0.05"], "ACGT")]


def test_fall_back(monkeypatch):
    which_called = []
    errors_called = []

    monkeypatch.setattr(
        nanopore_sim.shutil, "which", lambda t: which_called.append(t) or None
    )
    monkeypatch.setattr(
        nanopore_sim,
        "simulate_errors",
        lambda seq, rate, rng=None: errors_called.append((seq, rate, rng)) or "fallback",
    )
    monkeypatch.setattr(nanopore_sim, "_run_external", lambda *_: "boom")

    result = d2sim_adapter.simulate_d2sim("ACGT", error_rate=0.1)
    assert result == "fallback"
    assert which_called == ["d2sim"]
    assert errors_called and isinstance(errors_called[0][2], random.Random)


def test_external_error(monkeypatch, caplog):
    which_called = []
    run_called = []
    errors_called = []

    monkeypatch.setattr(
        nanopore_sim.shutil, "which", lambda t: which_called.append(t) or "/usr/bin/" + t
    )

    def fake_run(command, seq):
        run_called.append((command, seq))
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(nanopore_sim, "_run_external", fake_run)
    monkeypatch.setattr(
        nanopore_sim,
        "simulate_errors",
        lambda s, r, rng=None: errors_called.append((s, r, rng)) or "fallback",
    )

    with caplog.at_level(logging.WARNING):
        result = d2sim_adapter.simulate_d2sim("ACGT", error_rate=0.2)

    assert result == "fallback"
    assert which_called == ["d2sim"]
    assert run_called == [(["d2sim", "-e", "0.2"], "ACGT")]
    assert errors_called and isinstance(errors_called[0][2], random.Random)
    assert any("falling back" in rec.message for rec in caplog.records)


def test_command_not_found_warning(monkeypatch, caplog):
    errors_called = []
    monkeypatch.setattr(nanopore_sim.shutil, "which", lambda t: None)

    def boom(*_):
        raise AssertionError("_run_external should not be called")

    monkeypatch.setattr(nanopore_sim, "_run_external", boom)
    monkeypatch.setattr(
        nanopore_sim,
        "simulate_errors",
        lambda seq, rate, rng=None: errors_called.append((seq, rate, rng)) or "fallback",
    )

    with caplog.at_level(logging.WARNING):
        result = d2sim_adapter.simulate_d2sim("ACGT")

    assert result == "fallback"
    assert errors_called and isinstance(errors_called[0][2], random.Random)
    assert any(
        rec.levelno == logging.WARNING and "not found" in rec.message
        for rec in caplog.records
    )


def test_d2sim_class_run(monkeypatch):
    called = []

    def fake_run_external(cmd, seq):
        called.append((cmd, seq))
        return "ok"

    monkeypatch.setattr(d2sim_adapter, "_run_external", fake_run_external)

    result = d2sim_adapter._D2SIM.run("ACGT")
    assert result == "ok"
    assert called == [("d2sim", "ACGT")]


def test_channel_object(monkeypatch):
    from genecoder.channels.base import BaseChannel

    registry: dict[str, BaseChannel] = {}

    d2sim_adapter.register(lambda name, ch: registry.setdefault(name, ch))

    assert "d2sim" in registry
    assert isinstance(registry["d2sim"], BaseChannel)
