"""Simple channel error simulator for DNA sequences."""
from __future__ import annotations

import random
from typing import Protocol, Callable

from .random_utils import make_rng

from .channels.base import BaseChannel
from .simulators import register_simulator as _register_simulator


__all__ = ["simulate_errors", "RandomLike", "Channel", "register"]


class RandomLike(Protocol):
    def random(self) -> float: ...

    def choice(self, seq: list[str]) -> str: ...

from typing import Optional

NUCLEOTIDES = ["A", "T", "C", "G"]


def simulate_errors(seq: str, p_error: float, rng: Optional[random.Random] = None) -> str:

    """Introduce random substitution errors into *seq* with probability ``p_error``.

    Each nucleotide has an independent chance ``p_error`` of being replaced by a
    different random nucleotide.  ``p_error`` should be between 0.0 and 1.0.
    If ``rng`` is given, it will be used for randomness instead of the module
    :mod:`random` generator.
    """
    if not 0.0 <= p_error <= 1.0:
        raise ValueError("p_error must be between 0 and 1")

    if rng is None:
        rng = random.Random()

    result = []
    for nt in seq:
        if rng.random() < p_error:
            choices = [n for n in NUCLEOTIDES if n != nt]
            result.append(rng.choice(choices))

        else:
            result.append(nt)
    return "".join(result)




class Channel(BaseChannel):
    """Simple substitution error channel."""

    def __init__(self, error_rate: float = 0.05) -> None:
        self.error_rate = error_rate

    def simulate(self, sequence: str) -> str:
        return simulate_errors(sequence, self.error_rate, rng=make_rng())


def register(
    registrar: Callable[[str, BaseChannel], None] = _register_simulator,
) -> None:
    """Register the simple substitution error simulator."""

    registrar("simple", Channel())
