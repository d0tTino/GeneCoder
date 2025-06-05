"""Utilities for simulating random sequencing errors in DNA sequences."""
from __future__ import annotations

import random

NUCLEOTIDES = ["A", "T", "C", "G"]


def _random_substitution(nucleotide: str, rng: random.Random) -> str:
    """Return a random nucleotide different from the input."""
    choices = [n for n in NUCLEOTIDES if n != nucleotide]
    return rng.choice(choices)


def introduce_errors(
    sequence: str,
    substitution_prob: float = 0.0,
    insertion_prob: float = 0.0,
    deletion_prob: float = 0.0,
    rng: random.Random | None = None,
) -> str:
    """Introduce random substitutions, insertions and deletions into ``sequence``.

    Parameters
    ----------
    sequence:
        Input DNA sequence.
    substitution_prob:
        Probability of substituting each nucleotide with a random one.
    insertion_prob:
        Probability of inserting a random nucleotide after each position.
    deletion_prob:
        Probability of deleting each nucleotide.
    rng:
        Optional :class:`random.Random` instance for deterministic behaviour.

    Returns
    -------
    str
        The mutated DNA sequence.
    """
    if rng is None:
        rng = random.Random()

    mutated: list[str] = []
    for nt in sequence:
        # deletion
        if rng.random() < deletion_prob:
            continue

        # substitution
        if rng.random() < substitution_prob:
            nt = _random_substitution(nt, rng)

        mutated.append(nt)

        # insertion after the (possibly substituted) nucleotide
        if rng.random() < insertion_prob:
            mutated.append(rng.choice(NUCLEOTIDES))

    return "".join(mutated)


def apply_substitutions(sequence: str, prob: float, rng: random.Random | None = None) -> str:
    """Apply random substitutions to ``sequence`` with probability ``prob``."""
    return introduce_errors(sequence, substitution_prob=prob, rng=rng)


def apply_insertions(sequence: str, prob: float, rng: random.Random | None = None) -> str:
    """Insert random nucleotides into ``sequence`` with probability ``prob``."""
    return introduce_errors(sequence, insertion_prob=prob, rng=rng)


def apply_deletions(sequence: str, prob: float, rng: random.Random | None = None) -> str:
    """Delete nucleotides from ``sequence`` with probability ``prob``."""
    return introduce_errors(sequence, deletion_prob=prob, rng=rng)
