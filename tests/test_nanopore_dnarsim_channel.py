from genecoder.simulators.nanopore import NanoporeDNArSimChannel
import genecoder.simulators.nanopore as nanopore
import genecoder.random_utils as random_utils
import logging
import random


def test_fallback_deterministic(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    monkeypatch.setattr(nanopore.shutil, "which", lambda _: None)
    random_utils._RNG = None
    ch = NanoporeDNArSimChannel(error_rate=0.2)
    first = ch.simulate("ACGTACGTACGT")
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    random_utils._RNG = None
    second = ch.simulate("ACGTACGTACGT")
    assert first == second == "ACGAGTACCGT"


def test_cli_invocation(monkeypatch):
    called = []
    monkeypatch.setattr(nanopore.shutil, "which", lambda _: "/usr/bin/dnarsim")
    monkeypatch.setattr(nanopore, "_parse_env_options", lambda _: [])

    def fake_run(cmd, seq):
        called.append((cmd, seq))
        return "ok"

    monkeypatch.setattr(nanopore, "_run_external", fake_run)
    ch = NanoporeDNArSimChannel(error_rate=0.1, profile="r9")
    result = ch.simulate("ACGT")
    assert called == [(["dnarsim", "-e", "0.1", "-p", "r9"], "ACGT")]
    assert isinstance(result, str)


def test_missing_executable_warning(monkeypatch, caplog):
    called = []
    monkeypatch.setattr(nanopore.shutil, "which", lambda _: None)

    def fake_fallback(seq: str, rate: float, rng):
        called.append((seq, rate, rng))
        return "fallback"

    monkeypatch.setattr(
        nanopore.NanoporeDNArSimChannel,
        "_simulate_fallback",
        staticmethod(fake_fallback),
    )
    ch = NanoporeDNArSimChannel(error_rate=0.1)
    with caplog.at_level(logging.WARNING):
        result = ch.simulate("ACGT")

    assert result == "fallback"
    assert called and isinstance(called[0][2], random.Random)
    assert any("not found" in rec.message for rec in caplog.records)

