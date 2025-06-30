"""DNA replication simulator stub."""
from __future__ import annotations

from typing import Callable
from dataclasses import dataclass

from .base import BaseSimulator
from ..random_utils import make_rng
from ..error_simulation import introduce_errors
from ..channels.base import BaseChannel

__all__ = ["ReplicationSimulator", "register"]


@dataclass
class ReplicationSimulator(BaseSimulator):
    """Simplified DNA replication error model."""

    substitution_rate: float = 1e-4
    insertion_rate: float = 1e-5
    deletion_rate: float = 1e-5
    read_length: int = 0

    def simulate(self, sequence: str) -> str:
        rng = make_rng()
        return introduce_errors(
            sequence,
            substitution_prob=self.substitution_rate,
            insertion_prob=self.insertion_rate,
            deletion_prob=self.deletion_rate,
            rng=rng,
        )


def register(register_simulator: Callable[[str, BaseChannel], None]) -> None:
    register_simulator("replication", ReplicationSimulator())
