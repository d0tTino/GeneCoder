"""Built-in Illumina-like sequencing simulator.

This module implements a small Illumina error model dominated by base
substitutions.  Earlier versions exposed a single ``error_rate`` parameter
from which insertion and deletion probabilities were derived.  The model now
accepts separate ``substitution_rate``, ``insertion_rate`` and
``deletion_rate`` values which can also be loaded from named profiles.
"""
from __future__ import annotations

import random
from typing import Callable, Sequence

from .api import Simulator
from .random_utils import make_rng
from .simulators import register_simulator as _register_simulator
from .simulators.illumina.mutations import mutate_read
from .simulators.illumina.profiles import (
    ILLUMINA_PROFILES as _ILLUMINA_PROFILES,
    IlluminaProfile,
    _resolve_profile,
)
from .simulators.illumina.utils import consensus, poisson

ILLUMINA_PROFILES = _ILLUMINA_PROFILES

__all__ = ["simulate", "Channel", "register", "ILLUMINA_PROFILES"]


def _poisson(lam: float, rng: random.Random) -> int:
    """Return a Poisson-distributed integer with mean ``lam``."""

    return poisson(lam, rng)


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

    if quality_distribution is not None and quality_profile is None:
        if quality_distribution:
            quality_profile = tuple(
                rng.choice(quality_distribution) for _ in range(len(sequence))
            )
        else:
            quality_profile = None

    return mutate_read(
        sequence,
        quality_profile,
        rng,
        substitution_rate=substitution_prob,
        insertion_rate=insertion_prob,
        deletion_rate=deletion_prob,
        context_errors={},
    )


def simulate(
    sequence: str,
    substitution_rate: float | None = None,
    *,
    insertion_rate: float | None = None,
    deletion_rate: float | None = None,
    rng: random.Random | None = None,
    coverage_depth: float | None = None,
    quality_profile: Sequence[float] | None = None,
    quality_distribution: Sequence[float] | None = None,
    profile: str | None = None,
) -> str:
    """Return ``sequence`` mutated with Illumina-style errors.

    Parameters
    ----------
    sequence:
        Input DNA sequence.
    substitution_rate, insertion_rate, deletion_rate:
        Per-base error probabilities.  Missing values are filled from the
        named ``profile`` when provided, otherwise from the builtin defaults.
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
    profile:
        Optional profile name defined in :data:`ILLUMINA_PROFILES`.
    """

    prof_defaults, prof_data = _resolve_profile(profile or "hiseq")
    prof = prof_defaults
    substitution_rate = float(
        substitution_rate
        if substitution_rate is not None
        else (prof.substitution_rate if prof is not None else 0.001)
    )
    insertion_rate = float(
        insertion_rate
        if insertion_rate is not None
        else (prof.insertion_rate if prof is not None else 0.0001)
    )
    deletion_rate = float(
        deletion_rate
        if deletion_rate is not None
        else (prof.deletion_rate if prof is not None else 0.0001)
    )
    coverage_depth = float(
        coverage_depth
        if coverage_depth is not None
        else (prof.coverage if prof is not None else 1)
    )
    if prof_data:
        quality_profile = prof_data.get("quality_profile", quality_profile)

    if rng is None:
        rng = make_rng()

    coverage = max(1, poisson(coverage_depth, rng))
    reads = [
        _mutate_read(
            sequence,
            substitution_rate,
            insertion_rate,
            deletion_rate,
            quality_profile,
            quality_distribution,
            rng,
        )
        for _ in range(coverage)
    ]
    if coverage == 1:
        return reads[0]
    return consensus(reads)


class Channel(Simulator):
    """Channel applying the built-in Illumina-style error model."""

    def __init__(
        self,
        substitution_rate: float | None = None,
        *,
        insertion_rate: float | None = None,
        deletion_rate: float | None = None,
        coverage_depth: float | None = None,
        quality_profile: Sequence[float] | None = None,
        quality_distribution: Sequence[float] | None = None,
        profile: str | None = None,
    ) -> None:
        prof_defaults, prof_data = _resolve_profile(profile or "hiseq")
        prof: IlluminaProfile | None = prof_defaults
        self.substitution_rate = float(
            substitution_rate
            if substitution_rate is not None
            else (prof.substitution_rate if prof is not None else 0.001)
        )
        self.insertion_rate = float(
            insertion_rate
            if insertion_rate is not None
            else (prof.insertion_rate if prof is not None else 0.0001)
        )
        self.deletion_rate = float(
            deletion_rate
            if deletion_rate is not None
            else (prof.deletion_rate if prof is not None else 0.0001)
        )
        self.coverage_depth = float(
            coverage_depth
            if coverage_depth is not None
            else (prof.coverage if prof is not None else 1)
        )
        if prof_data:
            quality_profile = prof_data.get("quality_profile", quality_profile)
        self.quality_profile = (
            tuple(quality_profile) if quality_profile is not None else None
        )
        self.quality_distribution = (
            tuple(quality_distribution) if quality_distribution is not None else None
        )

    def simulate(self, sequence: str) -> str:  # pragma: no cover - thin wrapper
        return simulate(
            sequence,
            substitution_rate=self.substitution_rate,
            insertion_rate=self.insertion_rate,
            deletion_rate=self.deletion_rate,
            rng=make_rng(),
            coverage_depth=self.coverage_depth,
            quality_profile=self.quality_profile,
            quality_distribution=self.quality_distribution,
        )


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    """Register the simulator with the global registry."""

    registrar("illumina_builtin", Channel())
