"""RNA transcription simulator stub."""
from __future__ import annotations

from typing import Callable
from dataclasses import dataclass

from .base import BaseSimulator
from ..random_utils import make_rng
from ..error_simulation import introduce_errors
from ..channels.base import BaseChannel
from . import register_simulator as _register_simulator

__all__ = ["TranscriptionSimulator", "register"]


@dataclass
class TranscriptionSimulator(BaseSimulator):
    """Simplified transcription error model."""

    substitution_rate: float = 1e-4
    insertion_rate: float = 1e-5
    deletion_rate: float = 1e-5
    read_length: int = 0

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


def register(
    registrar: Callable[[str, BaseChannel], None] = _register_simulator,
) -> None:
    registrar("transcription", TranscriptionSimulator())
