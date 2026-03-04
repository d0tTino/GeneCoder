from __future__ import annotations

import random

from .mutation_primitives import NUCLEOTIDES, random_substitution


def introduce_errors(
    sequence: str,
    *,
    substitution_prob: float = 0.0,
    insertion_prob: float = 0.0,
    deletion_prob: float = 0.0,
    rng: random.Random,
) -> str:
    mutated: list[str] = []
    for nt in sequence:
        if nt.upper() not in NUCLEOTIDES:
            mutated.append(nt)
            continue
        if rng.random() < deletion_prob:
            continue
        if rng.random() < substitution_prob:
            nt = random_substitution(nt, rng)
        mutated.append(nt)
        if rng.random() < insertion_prob:
            mutated.append(rng.choice(NUCLEOTIDES))
    return "".join(mutated)
