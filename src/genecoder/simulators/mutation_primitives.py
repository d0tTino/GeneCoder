"""Shared mutation primitives used by simulator runtime modules."""
from __future__ import annotations

import random

NUCLEOTIDES = ["A", "T", "C", "G"]


def random_substitution(nucleotide: str, rng: random.Random) -> str:
    """Return a random nucleotide different from the input."""
    choices = [n for n in NUCLEOTIDES if n != nucleotide]
    return rng.choice(choices)
