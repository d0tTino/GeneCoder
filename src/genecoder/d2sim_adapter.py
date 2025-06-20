"""Adapter for the optional ``d2sim`` read simulator."""
from __future__ import annotations

import random
from typing import Callable, Any

from .nanopore_sim import _simulate_adapter


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
