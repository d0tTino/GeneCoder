"""Simple Illumina sequencing simulator."""
from __future__ import annotations

import random
from typing import Callable, Sequence

from ..random_utils import make_rng

from ..channels.base import BaseChannel
from ..error_simulation import introduce_errors

__all__ = ["IlluminaChannel", "register"]




class IlluminaChannel(BaseChannel):
    """Channel modeling basic Illumina read errors."""

    def __init__(
        self,
        substitution_rate: float = 0.001,
        insertion_rate: float = 0.0001,
        deletion_rate: float = 0.0001,
        coverage: int = 1,
        read_length: int = 150,
        quality_profile: Sequence[float] | None = None,
    ) -> None:
        self.substitution_rate = substitution_rate
        self.insertion_rate = insertion_rate
        self.deletion_rate = deletion_rate
        self.coverage = coverage
        self.read_length = read_length
        self.quality_profile = tuple(quality_profile) if quality_profile is not None else None

    def simulate(self, sequence: str) -> str:
        rng = make_rng()
        read = sequence[: self.read_length]
        return introduce_errors(
            read,
            substitution_prob=self.substitution_rate,
            insertion_prob=self.insertion_rate,
            deletion_prob=self.deletion_rate,
            rng=rng,
        )


def register(register_simulator: Callable[[str, BaseChannel], None]) -> None:
    register_simulator("illumina", IlluminaChannel())
