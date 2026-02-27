"""Mutation helpers for the Illumina simulator."""
from __future__ import annotations

from typing import Dict, Sequence
import random

try:  # Optional at runtime
    from numba import njit
except Exception:  # pragma: no cover - fallback when numba missing
    from typing import Callable, TypeVar, ParamSpec

    P = ParamSpec("P")
    R = TypeVar("R")

    def njit(*args: object, **kwargs: object) -> Callable[[Callable[P, R]], Callable[P, R]]:  # type: ignore[misc]
        def wrapper(func: Callable[P, R]) -> Callable[P, R]:
            return func

        return wrapper

from ..mutation_primitives import NUCLEOTIDES, random_substitution
from ..error_metrics import MutationObservation


__all__ = ["mutate_read"]


@njit(cache=True, forceobj=True)  # type: ignore[misc]
def _mutate_read_jit(
    read: str,
    quality: Sequence[float] | None,
    substitution_rate: float,
    insertion_rate: float,
    deletion_rate: float,
    context_errors: Dict[str, float],
    rng: random.Random,
    observation: MutationObservation | None = None,
) -> str:
    mutated: list[str] = []
    subs = 0
    ins = 0
    dels = 0
    for idx, nt in enumerate(read):
        if nt.upper() not in NUCLEOTIDES:
            mutated.append(nt)
            continue
        if rng.random() < deletion_rate:
            dels += 1
            continue

        sub_rate = (
            quality[idx] if quality is not None and idx < len(quality) else substitution_rate
        )
        if context_errors and idx > 0:
            ctx = read[idx - 1 : idx + 1].upper()
            sub_rate *= context_errors.get(ctx, 1.0)

        if rng.random() < sub_rate:
            nt = random_substitution(nt, rng)
            subs += 1

        mutated.append(nt)
        if rng.random() < insertion_rate:
            mutated.append(rng.choice(NUCLEOTIDES))
            ins += 1

    if observation is not None:
        observation.extend(subs, ins, dels, len(read))
    return "".join(mutated)


def mutate_read(
    read: str,
    quality: Sequence[float] | None,
    rng: random.Random,
    *,
    substitution_rate: float,
    insertion_rate: float,
    deletion_rate: float,
    context_errors: Dict[str, float],
    observation: MutationObservation | None = None,
) -> str:
    """Return a mutated ``read`` using the configured error rates."""

    return _mutate_read_jit(
        read,
        quality,
        substitution_rate,
        insertion_rate,
        deletion_rate,
        context_errors,
        rng,
        observation,
    )
