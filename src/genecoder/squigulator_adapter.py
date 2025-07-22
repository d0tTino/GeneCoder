"""Adapter for the optional ``squigulator`` read simulator."""
from __future__ import annotations

import random
from typing import Callable

from .api import Simulator
from .random_utils import make_rng
from .nanopore_sim import _simulate_adapter, _run_external
from .simulators import register_simulator as _register_simulator


class _SQUIGULATOR:
    """Internal helper to invoke the :mod:`squigulator` binary."""

    command = "squigulator"

    @staticmethod
    def run(sequence: str) -> str:
        """Run ``squigulator`` on ``sequence`` via :func:`_run_external`."""

        return _run_external(_SQUIGULATOR.command, sequence)


def simulate_squigulator(
    sequence: str,
    error_rate: float = 0.05,
    rng: random.Random | None = None,
) -> str:
    """Use ``squigulator`` if available, else fall back to :func:`simulate_errors`."""

    if rng is None:
        rng = make_rng()

    return _simulate_adapter("squigulator", sequence, error_rate, rng, None)


class SquigulatorChannel(Simulator):
    """Channel wrapper for the optional ``squigulator`` simulator."""

    def __init__(self, error_rate: float = 0.05) -> None:
        self.error_rate = error_rate

    def simulate(self, sequence: str) -> str:
        return simulate_squigulator(sequence, error_rate=self.error_rate, rng=make_rng())


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    """Register the ``squigulator`` simulator."""

    registrar("squigulator", SquigulatorChannel())
