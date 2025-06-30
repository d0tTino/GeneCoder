"""Advanced Nanopore sequencing simulator with homopolymer bias."""
from __future__ import annotations

import random
from typing import Callable, Sequence

from .base import BaseSimulator

from ..random_utils import make_rng

from ..channels.base import BaseChannel

__all__ = ["AdvancedNanoporeChannel", "register"]


def _simulate_homopolymer_errors(
    sequence: str,
    substitution_rate: float,
    insertion_rate: float,
    deletion_rate: float,
    homopolymer_factor: float,
    rng: random.Random,
) -> str:
    result: list[str] = []
    last = ""
    run = 0
    for nt in sequence:
        if nt == last:
            run += 1
        else:
            run = 1
            last = nt
        sub_prob = substitution_rate
        ins_prob = insertion_rate
        del_prob = deletion_rate
        if run >= 3:
            ins_prob *= homopolymer_factor
            del_prob *= homopolymer_factor
        if rng.random() < del_prob:
            continue
        if rng.random() < sub_prob:
            nt = rng.choice([b for b in "ATCG" if b != nt])
        result.append(nt)
        if rng.random() < ins_prob:
            result.append(rng.choice(list("ATCG")))
    return "".join(result)


class AdvancedNanoporeChannel(BaseSimulator):
    """Nanopore channel with simple homopolymer indel bias."""

    def __init__(
        self,
        substitution_rate: float = 0.02,
        insertion_rate: float = 0.04,
        deletion_rate: float = 0.04,
        homopolymer_factor: float = 2.0,
        coverage: int = 1,
        read_length: int = 500,
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
        self.homopolymer_factor = homopolymer_factor

    def simulate(self, sequence: str) -> str:
        rng = make_rng()
        read_length = self.get_read_length(sequence)
        read = sequence[:read_length]
        return _simulate_homopolymer_errors(
            read,
            substitution_rate=self.substitution_rate,
            insertion_rate=self.insertion_rate,
            deletion_rate=self.deletion_rate,
            homopolymer_factor=self.homopolymer_factor,
            rng=rng,
        )


def register(register_simulator: Callable[[str, BaseChannel], None]) -> None:
    register_simulator("adv_nanopore", AdvancedNanoporeChannel())
