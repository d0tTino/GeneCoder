"""Simple Illumina sequencing simulator."""
from __future__ import annotations

from typing import Callable, Sequence, Dict, Iterable
import random

from .base import BaseSimulator

from ..random_utils import make_rng
from ..api import Simulator
from ..error_simulation import _random_substitution, NUCLEOTIDES
from ..nanopore_sim import simulate_d2sim
from . import register_simulator as _register_simulator

__all__ = ["IlluminaChannel", "IlluminaD2SimChannel", "register"]


class IlluminaChannel(BaseSimulator):
    """Channel modeling basic Illumina read errors."""

    def __init__(
        self,
        substitution_rate: float = 0.001,
        insertion_rate: float = 0.0001,
        deletion_rate: float = 0.0001,
        coverage: int = 1,
        read_length: int = 150,
        quality_profile: Sequence[float] | None = None,
        context_errors: Dict[str, float] | None = None,
    ) -> None:
        super().__init__(
            substitution_rate=substitution_rate,
            insertion_rate=insertion_rate,
            deletion_rate=deletion_rate,
            coverage=coverage,
            read_length=read_length,
            quality_profile=quality_profile,
        )
        self.context_errors = {
            k.upper(): float(v) for k, v in (context_errors or {}).items()
        }

    def _mutate_read(
        self, read: str, quality: Sequence[float] | None, rng: random.Random
    ) -> str:
        mutated = []
        for idx, nt in enumerate(read):
            if rng.random() < self.deletion_rate:
                continue

            sub_rate = (
                quality[idx] if quality is not None and idx < len(quality) else self.substitution_rate
            )
            if self.context_errors and idx > 0:
                ctx = read[idx - 1 : idx + 1].upper()
                sub_rate *= self.context_errors.get(ctx, 1.0)

            if rng.random() < sub_rate:
                nt = _random_substitution(nt, rng)

            mutated.append(nt)
            if rng.random() < self.insertion_rate:
                mutated.append(rng.choice(NUCLEOTIDES))

        return "".join(mutated)

    @staticmethod
    def _consensus(reads: Iterable[str]) -> str:
        reads = list(reads)
        if not reads:
            return ""
        length = max(len(r) for r in reads)
        result = []
        for i in range(length):
            counts: Dict[str, int] = {}
            for r in reads:
                if i < len(r):
                    base = r[i]
                    counts[base] = counts.get(base, 0) + 1
            if counts:
                result.append(max(counts, key=lambda k: counts[k]))
        return "".join(result)

    def simulate(self, sequence: str) -> str:
        rng = make_rng()
        read_length = self.get_read_length(sequence)
        read = sequence[:read_length]
        quality = self.get_quality_profile(sequence, read_length)
        coverage = max(1, self.get_coverage(sequence))
        reads = [self._mutate_read(read, quality, rng) for _ in range(coverage)]
        if coverage == 1:
            return reads[0]
        return self._consensus(reads)


class IlluminaD2SimChannel(Simulator):
    """Wrapper using the external ``d2sim`` simulator."""

    def __init__(self, error_rate: float = 0.05) -> None:
        self.error_rate = error_rate

    def simulate(self, sequence: str) -> str:
        return simulate_d2sim(sequence, error_rate=self.error_rate, rng=make_rng())


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    registrar("illumina", IlluminaChannel())
    registrar("illumina_d2sim", IlluminaD2SimChannel())
