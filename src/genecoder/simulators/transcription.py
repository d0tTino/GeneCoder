"""RNA transcription simulator stub."""
from __future__ import annotations

from typing import Callable, Sequence

from .base import BaseSimulator
from ..random_utils import make_rng
from ..error_simulation import introduce_errors
from ..channels.base import BaseChannel

__all__ = ["TranscriptionSimulator", "register"]


class TranscriptionSimulator(BaseSimulator):
    """Simplified transcription error model."""

    def __init__(
        self,
        substitution_rate: float = 1e-4,
        insertion_rate: float = 1e-5,
        deletion_rate: float = 1e-5,
        coverage: int = 1,
        quality_profile: Sequence[float] | None = None,
    ) -> None:
        super().__init__(
            substitution_rate=substitution_rate,
            insertion_rate=insertion_rate,
            deletion_rate=deletion_rate,
            coverage=coverage,
            read_length=0,
            quality_profile=quality_profile,
        )

    def simulate(self, sequence: str) -> str:
        rng = make_rng()
        dna = introduce_errors(
            sequence,
            substitution_prob=self.substitution_rate,
            insertion_prob=self.insertion_rate,
            deletion_prob=self.deletion_rate,
            rng=rng,
        )
        return dna.replace("T", "U")


def register(register_simulator: Callable[[str, BaseChannel], None]) -> None:
    register_simulator("transcription", TranscriptionSimulator())
