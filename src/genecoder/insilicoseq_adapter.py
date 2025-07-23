"""Adapter for the optional ``InSilicoSeq`` Illumina simulator."""
from __future__ import annotations

import random
from typing import Callable

from .api import Simulator
from .random_utils import make_rng
from .nanopore_sim import _simulate_adapter, _run_external
from .simulators import register_simulator as _register_simulator


class _InSilicoSeq:
    """Internal helper to invoke the ``iss`` binary."""

    command = "iss"

    @staticmethod
    def run(sequence: str) -> str:
        """Run ``iss`` on ``sequence`` via :func:`_run_external`."""
        return _run_external(_InSilicoSeq.command, sequence)


def simulate_insilicoseq(
    sequence: str,
    error_rate: float = 0.05,
    rng: random.Random | None = None,
) -> str:
    """Use ``InSilicoSeq`` if available, else fall back to :func:`simulate_errors`."""

    if rng is None:
        rng = make_rng()

    return _simulate_adapter("insilicoseq", sequence, error_rate, rng)


class InSilicoSeqChannel(Simulator):
    """Channel wrapper for the optional ``InSilicoSeq`` simulator."""

    def __init__(self, error_rate: float = 0.05) -> None:
        self.error_rate = error_rate

    def simulate(self, sequence: str) -> str:
        return simulate_insilicoseq(sequence, error_rate=self.error_rate, rng=make_rng())


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    """Register the ``InSilicoSeq`` simulator."""

    registrar("insilicoseq", InSilicoSeqChannel())
