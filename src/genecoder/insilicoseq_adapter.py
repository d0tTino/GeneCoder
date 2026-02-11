"""Adapter for the optional ``InSilicoSeq`` Illumina simulator."""
from __future__ import annotations

import random
from typing import Callable

from .plugin_api import Simulator
from .simulators.illumina import (
    IlluminaInSilicoSeqChannel as _IlluminaInSilicoSeqChannel,
    simulate_insilicoseq as _simulate_insilicoseq,
)
from .simulators import register_simulator as _register_simulator


MISEQ_PROFILE = "MiSeq"
HISEQ_PROFILE = "HiSeq"

# Mapping of user friendly preset names to ``insilicoseq`` profile strings.
INSILICOSEQ_PROFILES = {
    "miseq": MISEQ_PROFILE,
    "hiseq": HISEQ_PROFILE,
}


def simulate_insilicoseq(
    sequence: str,
    error_rate: float = 0.05,
    rng: random.Random | None = None,
    profile: str | None = None,
    *,
    seed: int | None = None,
) -> str:
    """Use ``InSilicoSeq`` if available, else fall back to ``IlluminaChannel``.

    The ``rng`` parameter is accepted for API compatibility but ignored.
    """

    if profile:
        profile = INSILICOSEQ_PROFILES.get(profile.lower(), profile)
    if seed is None:
        return _simulate_insilicoseq(
            sequence, error_rate=error_rate, profile=profile
        )
    return _simulate_insilicoseq(
        sequence, error_rate=error_rate, profile=profile, seed=seed
    )


class InSilicoSeqChannel(_IlluminaInSilicoSeqChannel):
    """Channel wrapper for the optional ``InSilicoSeq`` simulator."""

    def __init__(
        self, error_rate: float = 0.05, profile: str | None = None
    ) -> None:
        if profile:
            profile = INSILICOSEQ_PROFILES.get(profile.lower(), profile)
        super().__init__(error_rate=error_rate, profile=profile)


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    """Register the ``InSilicoSeq`` simulator."""

    registrar("insilicoseq", InSilicoSeqChannel())
