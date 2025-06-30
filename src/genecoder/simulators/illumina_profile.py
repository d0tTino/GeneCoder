"""Illumina simulator using quality profile for per-base error rates."""
from __future__ import annotations

from typing import Callable, Sequence

from .base import BaseSimulator
from ..random_utils import make_rng
from ..channels.base import BaseChannel

__all__ = ["IlluminaProfileChannel", "register"]


class IlluminaProfileChannel(BaseSimulator):
    """Illumina simulator with per-base quality influenced substitutions."""

    def __init__(
        self,
        substitution_rate: float = 0.001,
        insertion_rate: float = 0.0001,
        deletion_rate: float = 0.0001,
        coverage: int = 1,
        read_length: int = 150,
        quality_profile: Sequence[float] | None = None,
    ) -> None:
        super().__init__(
            substitution_rate=substitution_rate,
            insertion_rate=insertion_rate,
            deletion_rate=deletion_rate,
            coverage=coverage,
            read_length=read_length,
            quality_profile=quality_profile,
        )

    def _quality_error_prob(self, q: float) -> float:
        """Return error probability from a phred quality value."""
        return 10 ** (-q / 10)

    def simulate(self, sequence: str) -> str:
        rng = make_rng()
        read_length = self.get_read_length(sequence)
        read = sequence[:read_length]
        q_profile = self.get_quality_profile(read, read_length)
        result: list[str] = []
        for idx, nt in enumerate(read):
            sub_prob = self.substitution_rate
            if q_profile:
                sub_prob = min(1.0, sub_prob + self._quality_error_prob(q_profile[idx]))
            if sub_prob + self.insertion_rate + self.deletion_rate > 1.0:
                raise ValueError("sum of error probabilities must not exceed 1")
            if rng.random() < self.deletion_rate:
                continue
            if rng.random() < sub_prob:
                nt = rng.choice([b for b in "ATCG" if b != nt])
            result.append(nt)
            if rng.random() < self.insertion_rate:
                result.append(rng.choice(list("ATCG")))
        return "".join(result)


def register(register_simulator: Callable[[str, BaseChannel], None]) -> None:
    register_simulator("illumina_profile", IlluminaProfileChannel())
