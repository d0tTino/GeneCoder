import logging
import subprocess
import random
import pytest

from genecoder import insilicoseq_adapter, desp_adapter, nanopore_sim
import genecoder.simulators.illumina as illumina

ADAPTERS = {
    "insilicoseq": (
        insilicoseq_adapter.simulate_insilicoseq,
        None,
        "insilicoseq",
    ),
    "desp": (
        desp_adapter.simulate_desp,
        desp_adapter._DeSP,
        "desp",
    ),
}


@pytest.mark.parametrize("name", ADAPTERS.keys())
def test_run_external(monkeypatch, name):
    func, cls, cmd = ADAPTERS[name]
    which_called = []
    run_called = []

    def fake_which(target):
        which_called.append(target)
        return "/usr/bin/" + target

    def fake_run(command, seq):
        run_called.append((command, seq))
        return "external"

    if name == "insilicoseq":
        monkeypatch.setattr(illumina.shutil, "which", fake_which)
        monkeypatch.setattr(illumina, "_run_external", fake_run)
    else:
        monkeypatch.setattr(nanopore_sim.shutil, "which", fake_which)
        monkeypatch.setattr(nanopore_sim, "_run_external", fake_run)

    result = func("ACGT")
    assert result == "external"
    assert which_called == [cmd]
    assert run_called == [([cmd, "-e", "0.05"], "ACGT")]


@pytest.mark.parametrize("name", ADAPTERS.keys())
def test_fall_back(monkeypatch, name):
    func, cls, cmd = ADAPTERS[name]
    which_called = []
    errors_called = []

    if name == "insilicoseq":
        monkeypatch.setattr(
            illumina.shutil, "which", lambda t: which_called.append(t) or None
        )
        monkeypatch.setattr(
            illumina,
            "_run_external",
            lambda *_: (_ for _ in ()).throw(AssertionError("_run_external should not be called")),
        )
        monkeypatch.setattr(
            illumina.IlluminaChannel,
            "simulate",
            lambda self, s: errors_called.append((self, s)) or "fallback",
        )
    else:
        monkeypatch.setattr(
            nanopore_sim.shutil, "which", lambda t: which_called.append(t) or None
        )
        monkeypatch.setattr(
            nanopore_sim,
            "simulate_errors",
            lambda seq, rate, rng=None: errors_called.append((seq, rate, rng))
            or "fallback",
        )
        monkeypatch.setattr(nanopore_sim, "_run_external", lambda *_: "boom")

    result = func("ACGT", error_rate=0.1)
    assert result == "fallback"
    assert which_called == [cmd]
    assert errors_called
    if name != "insilicoseq":
        assert isinstance(errors_called[0][2], random.Random)


@pytest.mark.parametrize("name", ADAPTERS.keys())
def test_external_error(monkeypatch, caplog, name):
    func, cls, cmd = ADAPTERS[name]
    which_called = []
    run_called = []
    errors_called = []

    if name == "insilicoseq":
        monkeypatch.setattr(
            illumina.shutil, "which", lambda t: which_called.append(t) or "/usr/bin/" + t
        )

        def fake_run(command, seq):
            run_called.append((command, seq))
            raise subprocess.CalledProcessError(1, command)

        monkeypatch.setattr(illumina, "_run_external", fake_run)
        monkeypatch.setattr(
            illumina.IlluminaChannel,
            "simulate",
            lambda self, s: errors_called.append((self, s)) or "fallback",
        )
    else:
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
        result = func("ACGT", error_rate=0.2)

    assert result == "fallback"
    assert which_called == [cmd]
    assert run_called == [([cmd, "-e", "0.2"], "ACGT")]
    assert errors_called
    if name != "insilicoseq":
        assert isinstance(errors_called[0][2], random.Random)
    assert any("falling back" in rec.message for rec in caplog.records)


@pytest.mark.parametrize("name", ADAPTERS.keys())
def test_command_not_found_warning(monkeypatch, caplog, name):
    func, cls, cmd = ADAPTERS[name]
    errors_called = []

    if name == "insilicoseq":
        monkeypatch.setattr(illumina.shutil, "which", lambda t: None)

        def boom(*_):
            raise AssertionError("_run_external should not be called")

        monkeypatch.setattr(illumina, "_run_external", boom)
        monkeypatch.setattr(
            illumina.IlluminaChannel,
            "simulate",
            lambda self, s: errors_called.append((self, s)) or "fallback",
        )
    else:
        monkeypatch.setattr(nanopore_sim.shutil, "which", lambda t: None)

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
    assert errors_called
    if name != "insilicoseq":
        assert isinstance(errors_called[0][2], random.Random)
    assert any(
        rec.levelno == logging.WARNING and "not found" in rec.message for rec in caplog.records
    )


@pytest.mark.parametrize("name", ADAPTERS.keys())
def test_class_run(monkeypatch, name):
    func, cls, cmd = ADAPTERS[name]
    if cls is None:
        pytest.skip("no direct command helper for insilicoseq")
    called = []

    def fake_run_external(c, seq):
        called.append((c, seq))
        return "ok"

    monkeypatch.setattr(cls, "command", cmd)
    target_module = insilicoseq_adapter if name == "insilicoseq" else desp_adapter
    monkeypatch.setattr(target_module, "_run_external", fake_run_external)

    result = cls.run("ACGT")
    assert result == "ok"
    assert called == [(cmd, "ACGT")]


@pytest.mark.parametrize("name", ADAPTERS.keys())
def test_channel_object(monkeypatch, name):
    from genecoder.channels.base import BaseChannel

    module = insilicoseq_adapter if name == "insilicoseq" else desp_adapter
    registry: dict[str, BaseChannel] = {}
    module.register(lambda n, ch: registry.setdefault(n, ch))

    assert name in registry
    assert isinstance(registry[name], BaseChannel)

