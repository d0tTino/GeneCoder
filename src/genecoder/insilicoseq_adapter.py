"""Adapter for the optional ``InSilicoSeq`` Illumina simulator."""
from __future__ import annotations

import random
from typing import Callable

from .api import Simulator
from .simulators.illumina import (
    IlluminaInSilicoSeqChannel as _IlluminaInSilicoSeqChannel,
    simulate_insilicoseq as _simulate_insilicoseq,
)
from .simulators import register_simulator as _register_simulator


def simulate_insilicoseq(
    sequence: str,
    error_rate: float = 0.05,
    rng: random.Random | None = None,
) -> str:
    """Use ``InSilicoSeq`` if available, else fall back to ``IlluminaChannel``.

    The ``rng`` parameter is accepted for API compatibility but ignored.
    """

    return _simulate_insilicoseq(sequence, error_rate=error_rate)


class InSilicoSeqChannel(_IlluminaInSilicoSeqChannel):
    """Channel wrapper for the optional ``InSilicoSeq`` simulator."""

    def __init__(self, error_rate: float = 0.05) -> None:
        super().__init__(error_rate=error_rate)


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    """Register the ``InSilicoSeq`` simulator."""

    registrar("insilicoseq", InSilicoSeqChannel())
