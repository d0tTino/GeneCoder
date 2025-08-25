"""Built-in Illumina-like sequencing simulator.

This module implements a small Illumina error model dominated by base
substitutions.  Earlier versions exposed a single ``error_rate`` parameter
from which insertion and deletion probabilities were derived.  The model now
accepts separate ``substitution_rate``, ``insertion_rate`` and
``deletion_rate`` values which can also be loaded from named profiles defined
in :mod:`configs/illumina.yml`.
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Callable, Sequence, Mapping

from .error_simulation import NUCLEOTIDES, _random_substitution
from .random_utils import make_rng
from .api import Simulator
from .simulators import register_simulator as _register_simulator

__all__ = ["simulate", "Channel", "register", "ILLUMINA_PROFILES"]


_DEFAULT_PROFILES: dict[str, dict[str, float | int]] = {
    "hiseq": {
        "substitution_rate": 0.0005,
        "insertion_rate": 0.00005,
        "deletion_rate": 0.00005,
        "coverage_depth": 1,
    },
    "miseq": {
        "substitution_rate": 0.001,
        "insertion_rate": 0.0001,
        "deletion_rate": 0.0001,
        "coverage_depth": 1,
    },
    "novaseq": {
        "substitution_rate": 0.0003,
        "insertion_rate": 0.00003,
        "deletion_rate": 0.00003,
        "coverage_depth": 1,
    },
    "nova": {
        "substitution_rate": 0.0003,
        "insertion_rate": 0.00003,
        "deletion_rate": 0.00003,
        "coverage_depth": 1,
    },
}

try:  # pragma: no cover - optional dependency
    import yaml

    _cfg_dir = Path(__file__).resolve().parents[2] / "configs"
    with open(_cfg_dir / "illumina.yml", "r", encoding="utf-8") as _fh:
        _data = yaml.safe_load(_fh) or {}
    if isinstance(_data, Mapping):
        ILLUMINA_PROFILES: dict[str, dict[str, float | int]] = {
            str(name): {
                "substitution_rate": float(params.get("substitution_rate", 0.001)),
                "insertion_rate": float(params.get("insertion_rate", 0.0001)),
                "deletion_rate": float(params.get("deletion_rate", 0.0001)),
                "coverage_depth": int(params.get("coverage_depth", 1)),
            }
            for name, params in _data.items()
            if isinstance(params, Mapping)
        }
    else:  # pragma: no cover - unexpected structure
        ILLUMINA_PROFILES = _DEFAULT_PROFILES
except Exception:  # pragma: no cover - fall back to defaults
    ILLUMINA_PROFILES = _DEFAULT_PROFILES


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
    substitution_rate: float | None = None,
    *,
    insertion_rate: float | None = None,
    deletion_rate: float | None = None,
    rng: random.Random | None = None,
    coverage_depth: int | None = None,
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

    prof = ILLUMINA_PROFILES.get(profile or "hiseq", {})
    substitution_rate = float(
        substitution_rate
        if substitution_rate is not None
        else prof.get("substitution_rate", 0.001)
    )
    insertion_rate = float(
        insertion_rate
        if insertion_rate is not None
        else prof.get("insertion_rate", 0.0001)
    )
    deletion_rate = float(
        deletion_rate
        if deletion_rate is not None
        else prof.get("deletion_rate", 0.0001)
    )
    coverage_depth = int(
        coverage_depth
        if coverage_depth is not None
        else int(prof.get("coverage_depth", 1))
    )

    if rng is None:
        rng = make_rng()

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
        for _ in range(max(1, coverage_depth))
    ]
    if coverage_depth <= 1:
        return reads[0]
    return _consensus(reads)


class Channel(Simulator):
    """Channel applying the built-in Illumina-style error model."""

    def __init__(
        self,
        substitution_rate: float | None = None,
        *,
        insertion_rate: float | None = None,
        deletion_rate: float | None = None,
        coverage_depth: int | None = None,
        quality_profile: Sequence[float] | None = None,
        quality_distribution: Sequence[float] | None = None,
        profile: str | None = None,
    ) -> None:
        prof = ILLUMINA_PROFILES.get(profile or "hiseq", {})
        self.substitution_rate = float(
            substitution_rate
            if substitution_rate is not None
            else prof.get("substitution_rate", 0.001)
        )
        self.insertion_rate = float(
            insertion_rate
            if insertion_rate is not None
            else prof.get("insertion_rate", 0.0001)
        )
        self.deletion_rate = float(
            deletion_rate
            if deletion_rate is not None
            else prof.get("deletion_rate", 0.0001)
        )
        self.coverage_depth = int(
            coverage_depth
            if coverage_depth is not None
            else int(prof.get("coverage_depth", 1))
        )
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
