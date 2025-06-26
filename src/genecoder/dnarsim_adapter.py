"""Adapter for the optional ``dnarsim`` read simulator."""
from __future__ import annotations

import random
from typing import Callable

from .channels.base import BaseChannel
from .random_utils import make_rng
from .nanopore_sim import _simulate_adapter, _run_external


class _DNARSIM:
    """Internal helper to invoke the :mod:`dnarsim` binary."""

    command = "dnarsim"

    @staticmethod
    def run(sequence: str) -> str:
        """Run ``dnarsim`` on ``sequence`` via :func:`_run_external`."""

        return _run_external(_DNARSIM.command, sequence)


def simulate_dnarsim(
    sequence: str,
    error_rate: float = 0.05,
    rng: random.Random | None = None,
) -> str:
    """Use ``dnarsim`` if available, else fall back to :func:`simulate_errors`."""

    if rng is None:
        rng = make_rng()

    return _simulate_adapter("dnarsim", sequence, error_rate, rng)


class DNArSimChannel(BaseChannel):
    """Channel wrapper for the optional ``dnarsim`` simulator."""

    def __init__(self, error_rate: float = 0.05) -> None:
        self.error_rate = error_rate

    def simulate(self, sequence: str) -> str:
        return simulate_dnarsim(sequence, error_rate=self.error_rate, rng=make_rng())


def register(register_simulator: Callable[[str, BaseChannel], None]) -> None:
    """Register the ``dnarsim`` simulator."""

    register_simulator("dnarsim", DNArSimChannel())
