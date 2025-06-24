"""Adapter for the optional ``d2sim`` read simulator."""
from __future__ import annotations

import random
from typing import Callable

from .channels.base import BaseChannel

from .nanopore_sim import _simulate_adapter, _run_external, _make_rng


class _D2SIM:
    """Internal helper to invoke the :mod:`d2sim` binary."""

    command = "d2sim"

    @staticmethod
    def run(sequence: str) -> str:
        """Run ``d2sim`` on ``sequence`` via :func:`_run_external`."""

        return _run_external(_D2SIM.command, sequence)


def simulate_d2sim(
    sequence: str,
    error_rate: float = 0.05,
    rng: random.Random | None = None,
) -> str:
    """Use ``d2sim`` if available, else fall back to :func:`simulate_errors`."""

    if rng is None:
        rng = _make_rng()

    return _simulate_adapter("d2sim", sequence, error_rate, rng)


class D2SimChannel(BaseChannel):
    """Channel wrapper for the optional ``d2sim`` simulator."""

    def __init__(self, error_rate: float = 0.05) -> None:
        self.error_rate = error_rate

    def simulate(self, sequence: str) -> str:
        return simulate_d2sim(sequence, error_rate=self.error_rate, rng=_make_rng())


def register(register_simulator: Callable[[str, BaseChannel], None]) -> None:
    """Register the ``d2sim`` simulator."""

    register_simulator("d2sim", D2SimChannel())
