from __future__ import annotations

import logging
import random

import genecoder.random_utils as random_utils
import genecoder.simulators.nanopore as nanopore
import genecoder.simulators.nanopore_external as nanopore_external
from genecoder.simulators.nanopore import NanoporeDNArSimChannel


def test_fallback_deterministic(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    monkeypatch.setattr(
        nanopore_external,
        "run_dnarsim_cli",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("fallback")),
    )
    random_utils._RNG = None
    ch = NanoporeDNArSimChannel(error_rate=0.2)
    first = ch.simulate("ACGTACGTACGT")
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    random_utils._RNG = None
    second = ch.simulate("ACGTACGTACGT")
    assert first == second == "ACGAGTACCGT"


def test_cli_invocation(monkeypatch):
    called: list[tuple[str, float | None, str | None]] = []

    def fake_cli(sequence: str, error_rate: float, profile: str | None, **_kw) -> str:
        called.append((sequence, error_rate, profile))
        return "ok"

    monkeypatch.setattr(nanopore_external, "run_dnarsim_cli", fake_cli)
    monkeypatch.setattr(nanopore, "run_dnarsim_cli", fake_cli)
    ch = NanoporeDNArSimChannel(error_rate=0.1, profile="r9")
    result = ch.simulate("ACGT")
    assert called == [("ACGT", 0.1, "r9")]
    assert isinstance(result, str)


def test_missing_executable_warning(monkeypatch, caplog):
    called = []

    def fake_fallback(sequence: str, error_rate: float, rng: random.Random) -> str:
        called.append((sequence, error_rate, rng))
        return "fallback"

    monkeypatch.setattr(nanopore_external.shutil, "which", lambda _: None)
    monkeypatch.setattr(nanopore, "run_dnarsim_cli", nanopore_external.run_dnarsim_cli)
    monkeypatch.setattr(nanopore, "_simulate_fallback_jit", staticmethod(fake_fallback))
    ch = NanoporeDNArSimChannel(error_rate=0.1)
    with caplog.at_level(logging.WARNING):
        result = ch.simulate("ACGT")

    assert result == "fallback"
    assert called and isinstance(called[0][2], random.Random)
    assert any("falling back" in rec.message for rec in caplog.records)

