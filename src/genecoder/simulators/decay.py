"""Simple strand degradation simulator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..plugin_api import Simulator
from ..random_utils import make_rng
from .mutation_primitives import random_substitution
from . import register_simulator as _register_simulator

__all__ = ["DegradationChannel", "register"]


@dataclass
class DegradationChannel(Simulator):
    """Channel modeling strand loss and base damage."""

    deletion_prob: float = 0.0
    substitution_prob: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.deletion_prob <= 1.0:
            raise ValueError("deletion_prob must be between 0 and 1")
        if not 0.0 <= self.substitution_prob <= 1.0:
            raise ValueError("substitution_prob must be between 0 and 1")

    def simulate(self, sequence: str) -> str:
        rng = make_rng()
        if rng.random() < self.deletion_prob:
            return ""
        mutated = [
            random_substitution(nt, rng) if rng.random() < self.substitution_prob else nt
            for nt in sequence
        ]
        return "".join(mutated)


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    """Register the degradation simulator."""

    registrar("decay", DegradationChannel())
