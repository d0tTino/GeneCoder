"""Tests for the external d2sim simulator adapter."""

from __future__ import annotations

import random

import pytest


@pytest.fixture()
def adapter_modules() -> tuple[object, object]:
    """Provide the d2sim adapter and simulator utilities."""

    from genecoder import d2sim_adapter
    from genecoder import simulator_utils

    return d2sim_adapter, simulator_utils


def test_simulate_d2sim_success(
    adapter_modules: tuple[object, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """simulate_d2sim uses external command when available."""
    d2sim_adapter, simulator_utils = adapter_modules
    monkeypatch.setattr(simulator_utils.shutil, "which", lambda cmd: "/usr/bin/d2sim")

    called: dict[str, list[str] | str] = {}

    def fake_run_external(cmd: list[str], sequence: str) -> str:
        called["cmd"] = cmd
        called["seq"] = sequence
        return "SIMULATED"

    monkeypatch.setattr(simulator_utils, "_run_external", fake_run_external)

    result = d2sim_adapter.simulate_d2sim("ACGT", rng=random.Random(0))

    assert result == "SIMULATED"
    assert called["cmd"][0] == "d2sim"
    assert called["seq"] == "ACGT"


def test_simulate_d2sim_fallback(
    adapter_modules: tuple[object, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """simulate_d2sim falls back when command missing."""
    d2sim_adapter, simulator_utils = adapter_modules
    monkeypatch.setattr(simulator_utils.shutil, "which", lambda cmd: None)
    called: dict[str, bool] = {"simulate_errors": False}

    def fake_simulate_errors(seq: str, error_rate: float, rng: random.Random) -> str:
        called["simulate_errors"] = True
        return "FALLBACK"

    def fake_run_external(*args: object, **kwargs: object) -> str:  # pragma: no cover
        raise AssertionError("_run_external should not be called")

    monkeypatch.setattr(simulator_utils, "simulate_errors", fake_simulate_errors)
    monkeypatch.setattr(simulator_utils, "_run_external", fake_run_external)

    result = d2sim_adapter.simulate_d2sim("ACGT", rng=random.Random(0))

    assert result == "FALLBACK"
    assert called["simulate_errors"]

