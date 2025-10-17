"""Generic utilities for the Illumina simulator."""
from __future__ import annotations

from typing import Dict, Iterable
import math
import random


__all__ = ["poisson", "consensus"]


def poisson(lam: float, rng: random.Random) -> int:
    """Return a Poisson-distributed integer with mean ``lam``."""

    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= rng.random()
    return k - 1


def consensus(reads: Iterable[str]) -> str:
    """Return a simple consensus sequence for ``reads``."""

    reads = list(reads)
    if not reads:
        return ""
    length = max(len(r) for r in reads)
    result = []
    for i in range(length):
        counts: Dict[str, int] = {}
        for r in reads:
            if i < len(r):
                base = r[i]
                counts[base] = counts.get(base, 0) + 1
        if counts:
            result.append(max(counts, key=lambda k: counts[k]))
    return "".join(result)
