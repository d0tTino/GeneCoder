"""Wrapper for the optional d2sim nanopore simulator."""
from __future__ import annotations

from typing import Callable

from ..random_utils import make_rng
from ..nanopore_sim import simulate_d2sim
from ..api import Simulator
from . import register_simulator as _register_simulator

__all__ = ["NanoporeChannel", "register"]


class NanoporeChannel(Simulator):
    """Channel that delegates to :mod:`d2sim` if installed."""

    def __init__(self, error_rate: float = 0.05) -> None:
        self.error_rate = error_rate

    def simulate(self, sequence: str) -> str:
        return simulate_d2sim(sequence, error_rate=self.error_rate, rng=make_rng())


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    registrar("nanopore_d2sim", NanoporeChannel())
