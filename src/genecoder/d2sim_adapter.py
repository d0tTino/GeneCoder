"""Adapter for the optional ``d2sim`` read simulator."""
from __future__ import annotations

import random
from typing import Callable, Any

from .nanopore_sim import _simulate_adapter, _run_external


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

    return _simulate_adapter("d2sim", sequence, error_rate, rng)


def register(register_simulator: Callable[[str, Callable[..., Any]], None]) -> None:
    """Register the ``d2sim`` simulator."""

    register_simulator("d2sim", simulate_d2sim)
