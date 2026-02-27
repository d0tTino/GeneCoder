"""Utility helpers for reproducible randomness."""
from __future__ import annotations

import random
from typing import Optional

from .runtime import RunContext, make_run_context

__all__ = ["make_rng", "reset_rng", "activate_run_context"]


_RNG: Optional[random.Random] = None
_LAST_SEED: Optional[int] = None
_ACTIVE_CONTEXT: RunContext | None = None


def activate_run_context(run_context: RunContext | None) -> None:
    """Register ``run_context`` as the implicit context for :func:`make_rng`."""

    global _ACTIVE_CONTEXT
    _ACTIVE_CONTEXT = run_context


def make_rng(run_context: RunContext | None = None, *, stage: str = "simulate") -> random.Random:
    """Return a module-wide :class:`~random.Random` seeded once."""

    global _RNG, _LAST_SEED
    context = run_context or _ACTIVE_CONTEXT or make_run_context()
    stage_name = stage if stage in {"global", "encode", "simulate", "decode"} else "simulate"
    seed = context.seed_for_stage(stage_name)  # type: ignore[arg-type]

    if _RNG is None or seed != _LAST_SEED:
        _RNG = random.Random(seed) if seed is not None else random.Random()
        _LAST_SEED = seed
    return _RNG


def reset_rng() -> None:
    """Reset the module's global RNG."""

    global _RNG, _LAST_SEED, _ACTIVE_CONTEXT
    _RNG = None
    _LAST_SEED = None
    _ACTIVE_CONTEXT = None
