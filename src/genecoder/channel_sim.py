"""Simple channel error simulator for DNA sequences."""
from __future__ import annotations

import random

NUCLEOTIDES = ["A", "T", "C", "G"]


def simulate_errors(seq: str, p_error: float) -> str:
    """Introduce random substitution errors into *seq* with probability ``p_error``.

    Each nucleotide has an independent chance ``p_error`` of being replaced by a
    different random nucleotide.  ``p_error`` should be between 0.0 and 1.0.
    """
    if not 0.0 <= p_error <= 1.0:
        raise ValueError("p_error must be between 0 and 1")

    result = []
    for nt in seq:
        if random.random() < p_error:
            choices = [n for n in NUCLEOTIDES if n != nt]
            result.append(random.choice(choices))
        else:
            result.append(nt)
    return "".join(result)
