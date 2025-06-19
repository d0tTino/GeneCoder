"""Simple channel error simulator for DNA sequences."""
from __future__ import annotations

import random
from typing import Protocol


__all__ = ["simulate_errors", "RandomLike"]


class RandomLike(Protocol):
    def random(self) -> float: ...

    def choice(self, seq: list[str]) -> str: ...

NUCLEOTIDES = ["A", "T", "C", "G"]


def simulate_errors(
    seq: str, p_error: float, rng: random.Random | None = None
) -> str:

    """Introduce random substitution errors into *seq* with probability ``p_error``.

    Each nucleotide has an independent chance ``p_error`` of being replaced by a
    different random nucleotide.  ``p_error`` should be between 0.0 and 1.0.
    If ``rng`` is given, it will be used for randomness instead of the module
    :mod:`random` generator.
    """
    if not 0.0 <= p_error <= 1.0:
        raise ValueError("p_error must be between 0 and 1")

    rand = rng or random

    result = []
    for nt in seq:
        if rand.random() < p_error:
            choices = [n for n in NUCLEOTIDES if n != nt]
            result.append(rand.choice(choices))

        else:
            result.append(nt)
    return "".join(result)
