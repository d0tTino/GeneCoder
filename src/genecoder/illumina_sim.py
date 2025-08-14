"""Built-in Illumina-like sequencing simulator.

This module implements a very small Illumina error model dominated by
base substitutions.  The overall error ``error_rate`` controls the
probability of a substitution.  Insertion and deletion probabilities are
scaled down to one hundredth of this value to approximate the relatively
low indel rates of Illumina machines.
"""
from __future__ import annotations

import random
from typing import Callable, Sequence

from .error_simulation import NUCLEOTIDES, _random_substitution
from .random_utils import make_rng
from .api import Simulator
from .simulators import register_simulator as _register_simulator

__all__ = ["simulate", "Channel", "register"]


def _mutate_read(
    sequence: str,
    substitution_prob: float,
    insertion_prob: float,
    deletion_prob: float,
    quality_profile: Sequence[float] | None,
    quality_distribution: Sequence[float] | None,
    rng: random.Random,
) -> str:
    """Return ``sequence`` mutated using the provided probabilities."""

    mutated: list[str] = []
    for idx, nt in enumerate(sequence):
        if rng.random() < deletion_prob:
            continue

        if quality_profile is not None and idx < len(quality_profile):
            sub_prob = quality_profile[idx]
        elif quality_distribution is not None and len(quality_distribution) > 0:
            sub_prob = rng.choice(quality_distribution)
        else:
            sub_prob = substitution_prob
        if rng.random() < sub_prob:
            nt = _random_substitution(nt, rng)

        mutated.append(nt)

        if rng.random() < insertion_prob:
            mutated.append(rng.choice(NUCLEOTIDES))

    return "".join(mutated)


def _consensus(reads: Sequence[str]) -> str:
    """Return the per-base majority sequence from ``reads``."""

    if not reads:
        return ""
    length = max(len(r) for r in reads)
    result: list[str] = []
    for i in range(length):
        counts: dict[str, int] = {}
        for r in reads:
            if i < len(r):
                base = r[i]
                counts[base] = counts.get(base, 0) + 1
        if counts:
            result.append(max(counts, key=lambda b: counts.get(b, 0)))
    return "".join(result)


def simulate(
    sequence: str,
    error_rate: float = 0.001,
    rng: random.Random | None = None,
    coverage_depth: int = 1,
    quality_profile: Sequence[float] | None = None,
    quality_distribution: Sequence[float] | None = None,
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
        Optional :class:`random.Random` instance for deterministic behaviour.
    coverage_depth:
        Number of independent reads to generate. A majority vote consensus
        is returned when ``coverage_depth`` is greater than one.
    quality_profile:
        Optional list of position-specific substitution probabilities.
    quality_distribution:
        Optional list describing a distribution of substitution probabilities
        to sample for each base when ``quality_profile`` is not provided.
    """

    insertion_prob = error_rate / 100.0
    deletion_prob = error_rate / 100.0
    if rng is None:
        rng = make_rng()

    reads = [
        _mutate_read(
            sequence,
            error_rate,
            insertion_prob,
            deletion_prob,
            quality_profile,
            quality_distribution,
            rng,
        )
        for _ in range(max(1, coverage_depth))
    ]
    if coverage_depth <= 1:
        return reads[0]
    return _consensus(reads)


class Channel(Simulator):
    """Channel applying the built-in Illumina-style error model."""

    def __init__(
        self,
        error_rate: float = 0.001,
        coverage_depth: int = 1,
        quality_profile: Sequence[float] | None = None,
        quality_distribution: Sequence[float] | None = None,
    ) -> None:
        self.error_rate = error_rate
        self.coverage_depth = coverage_depth
        self.quality_profile = (
            tuple(quality_profile) if quality_profile is not None else None
        )
        self.quality_distribution = (
            tuple(quality_distribution) if quality_distribution is not None else None
        )

    def simulate(self, sequence: str) -> str:  # pragma: no cover - thin wrapper
        return simulate(
            sequence,
            self.error_rate,
            make_rng(),
            coverage_depth=self.coverage_depth,
            quality_profile=self.quality_profile,
            quality_distribution=self.quality_distribution,
        )


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    """Register the simulator with the global registry."""

    registrar("illumina_builtin", Channel())
