"""Wrapper for the optional d2sim nanopore simulator."""
from __future__ import annotations

from typing import Callable, Sequence, Dict, Iterable
import random

from ..random_utils import make_rng
from ..nanopore_sim import simulate_d2sim, simulate_desp
from ..api import Simulator
from .base import BaseChannel
from ..error_simulation import _random_substitution, NUCLEOTIDES
from . import register_simulator as _register_simulator

__all__ = ["NanoporeChannel", "NanoporeDeSPChannel", "register"]


class NanoporeChannel(BaseChannel):
    """Channel that delegates to :mod:`d2sim` if installed."""

    def __init__(
        self,
        error_rate: float = 0.05,
        *,
        substitution_rate: float = 0.0,
        insertion_rate: float = 0.0,
        deletion_rate: float = 0.0,
        coverage: int = 1,
        quality_profile: Sequence[float] | None = None,
        context_errors: Dict[str, float] | None = None,
    ) -> None:
        super().__init__(
            substitution_rate=substitution_rate,
            insertion_rate=insertion_rate,
            deletion_rate=deletion_rate,
            coverage=coverage,
        )
        self.error_rate = error_rate
        self.quality_profile = (
            tuple(quality_profile) if quality_profile is not None else None
        )
        self.context_errors = {
            k.upper(): float(v) for k, v in (context_errors or {}).items()
        }

    def simulate(self, sequence: str) -> str:
        rng = make_rng()
        quality = self.quality_profile
        coverage = max(1, self.get_coverage(sequence))
        reads = [
            _mutate_read(
                simulate_d2sim(sequence, error_rate=self.error_rate, rng=rng),
                quality,
                rng,
                self,
            )
            for _ in range(coverage)
        ]
        if coverage == 1:
            return reads[0]
        return _consensus(reads)


class NanoporeDeSPChannel(NanoporeChannel):
    """Channel wrapper using the external ``desp`` simulator."""

    def simulate(self, sequence: str) -> str:
        rng = make_rng()
        quality = self.quality_profile
        coverage = max(1, self.get_coverage(sequence))
        reads = [
            _mutate_read(
                simulate_desp(sequence, error_rate=self.error_rate, rng=rng),
                quality,
                rng,
                self,
            )
            for _ in range(coverage)
        ]
        if coverage == 1:
            return reads[0]
        return _consensus(reads)


def _mutate_read(
    read: str, quality: Sequence[float] | None, rng: random.Random, channel: NanoporeChannel
) -> str:
    mutated = []
    for idx, nt in enumerate(read):
        if rng.random() < channel.deletion_rate:
            continue

        sub_rate = (
            quality[idx] if quality is not None and idx < len(quality) else channel.substitution_rate
        )
        if channel.context_errors and idx > 0:
            ctx = read[idx - 1 : idx + 1].upper()
            sub_rate *= channel.context_errors.get(ctx, 1.0)

        if rng.random() < sub_rate:
            nt = _random_substitution(nt, rng)

        mutated.append(nt)
        if rng.random() < channel.insertion_rate:
            mutated.append(rng.choice(NUCLEOTIDES))

    return "".join(mutated)


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


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    registrar("nanopore_d2sim", NanoporeChannel())
    registrar("nanopore_desp", NanoporeDeSPChannel())

