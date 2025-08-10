"""Built-in Illumina-like sequencing simulator.

This module implements a very small Illumina error model dominated by
base substitutions.  The overall error ``error_rate`` controls the
probability of a substitution.  Insertion and deletion probabilities are
scaled down to one hundredth of this value to approximate the relatively
low indel rates of Illumina machines.
"""
from __future__ import annotations

import random
from typing import Callable

from .error_simulation import simulate_errors
from .random_utils import make_rng
from .api import Simulator
from .simulators import register_simulator as _register_simulator

__all__ = ["simulate", "Channel", "register"]


def simulate(
    sequence: str,
    error_rate: float = 0.001,
    rng: random.Random | None = None,
) -> str:
    """Return ``sequence`` mutated with Illumina-style errors.

    Parameters
    ----------
    sequence:
        Input DNA sequence.
    error_rate:
        Probability of substituting each nucleotide.  Insertion and
        deletion probabilities are ``error_rate / 100``.
    rng:
        Optional :class:`random.Random` instance for deterministic
        behaviour.
    """
    insertion_prob = error_rate / 100.0
    deletion_prob = error_rate / 100.0
    return simulate_errors(
        sequence,
        substitution_prob=error_rate,
        insertion_prob=insertion_prob,
        deletion_prob=deletion_prob,
        rng=rng,
    )


class Channel(Simulator):
    """Channel applying the built-in Illumina-style error model."""

    def __init__(self, error_rate: float = 0.001) -> None:
        self.error_rate = error_rate

    def simulate(self, sequence: str) -> str:  # pragma: no cover - thin wrapper
        return simulate(sequence, self.error_rate, make_rng())


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    """Register the simulator with the global registry."""

    registrar("illumina_builtin", Channel())
