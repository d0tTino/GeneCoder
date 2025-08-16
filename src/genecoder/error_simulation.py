"""Utilities for simulating random sequencing errors in DNA sequences."""
from __future__ import annotations

import random
from typing import Callable

from .random_utils import make_rng
from .api import Simulator
from .simulators import register_simulator as _register_simulator

__all__ = [
    "simulate_errors",
    "introduce_errors",
    "apply_substitutions",
    "apply_insertions",
    "apply_deletions",
    "Channel",
    "register",
    "INDEL_PROFILES",
]

NUCLEOTIDES = ["A", "T", "C", "G"]


# Preset substitution/indel probability profiles for :class:`Channel`.
INDEL_PROFILES: dict[str, dict[str, float]] = {
    # Typical Illumina error characteristics favour substitutions over indels.
    "illumina": {
        "substitution_prob": 0.002,
        "insertion_prob": 0.0001,
        "deletion_prob": 0.0001,
    },
    # Nanopore devices tend to produce higher indel rates.
    "nanopore": {
        "substitution_prob": 0.01,
        "insertion_prob": 0.02,
        "deletion_prob": 0.02,
    },
}


def _random_substitution(nucleotide: str, rng: random.Random) -> str:
    """Return a random nucleotide different from the input."""
    choices = [n for n in NUCLEOTIDES if n != nucleotide]
    return rng.choice(choices)


def simulate_errors(
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

    Raises
    ------
    ValueError
        If any of ``substitution_prob``, ``insertion_prob`` or ``deletion_prob``
        is outside the range [0.0, 1.0] or if their sum exceeds 1.0.

    Returns
    -------
    str
        The mutated DNA sequence.
    """
    if not 0.0 <= substitution_prob <= 1.0:
        raise ValueError("substitution_prob must be between 0 and 1")
    if not 0.0 <= insertion_prob <= 1.0:
        raise ValueError("insertion_prob must be between 0 and 1")
    if not 0.0 <= deletion_prob <= 1.0:
        raise ValueError("deletion_prob must be between 0 and 1")
    if substitution_prob + insertion_prob + deletion_prob > 1.0:
        raise ValueError("sum of error probabilities must not exceed 1")

    if rng is None:
        rng = make_rng()

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


# Backwards compatibility alias
introduce_errors = simulate_errors


def apply_substitutions(sequence: str, prob: float, rng: random.Random | None = None) -> str:
    """Apply random substitutions to ``sequence`` with probability ``prob``."""
    return simulate_errors(sequence, substitution_prob=prob, rng=rng)


def apply_insertions(sequence: str, prob: float, rng: random.Random | None = None) -> str:
    """Insert random nucleotides into ``sequence`` with probability ``prob``."""
    return simulate_errors(sequence, insertion_prob=prob, rng=rng)


def apply_deletions(sequence: str, prob: float, rng: random.Random | None = None) -> str:
    """Delete nucleotides from ``sequence`` with probability ``prob``."""
    return simulate_errors(sequence, deletion_prob=prob, rng=rng)




class Channel(Simulator):
    """Channel applying substitution, insertion and deletion errors."""

    def __init__(
        self,
        substitution_prob: float = 0.0,
        insertion_prob: float = 0.0,
        deletion_prob: float = 0.0,
        error_rate: float | None = None,
        profile: str | None = None,
    ) -> None:
        if profile is not None:
            params = INDEL_PROFILES.get(profile.lower())
            if params is not None:
                substitution_prob = params["substitution_prob"]
                insertion_prob = params["insertion_prob"]
                deletion_prob = params["deletion_prob"]
        if error_rate is not None:
            substitution_prob = error_rate
        self.substitution_prob = substitution_prob
        self.insertion_prob = insertion_prob
        self.deletion_prob = deletion_prob

    # compatibility with older API expecting ``error_rate``
    @property
    def error_rate(self) -> float:
        return self.substitution_prob

    @error_rate.setter
    def error_rate(self, value: float) -> None:
        self.substitution_prob = value

    def simulate(self, sequence: str) -> str:
        return simulate_errors(
            sequence,
            substitution_prob=self.substitution_prob,
            insertion_prob=self.insertion_prob,
            deletion_prob=self.deletion_prob,
            rng=make_rng(),
        )

    def with_profile(self, profile: str) -> "Channel":
        """Return a new channel configured to use ``profile``."""

        if profile.lower() not in INDEL_PROFILES:
            return type(self)(
                substitution_prob=self.substitution_prob,
                insertion_prob=self.insertion_prob,
                deletion_prob=self.deletion_prob,
            )
        return type(self)(profile=profile)


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    """Register built-in error simulators."""

    registrar("simple", Channel(substitution_prob=0.05))
    registrar("indel", Channel())
    registrar("none", Channel())
