"""Utility helpers for reproducible randomness."""
from __future__ import annotations

import os
import random
import logging
from typing import Optional

__all__ = ["make_rng", "reset_rng"]


logger = logging.getLogger(__name__)


_RNG: Optional[random.Random] = None
_LAST_SEED: Optional[int] = None


def make_rng() -> random.Random:
    """Return a module-wide :class:`~random.Random` seeded once.

    The RNG is seeded from the ``GENECODER_SIM_SEED`` environment variable
    on first invocation and reused for all subsequent calls.  If the
    environment variable is unset or invalid, a default RNG is created.
    """

    global _RNG, _LAST_SEED
    seed_env = os.getenv("GENECODER_SIM_SEED")
    seed: Optional[int]
    if seed_env is not None:
        try:
            seed = int(seed_env)
        except ValueError:
            logger.warning(
                "Invalid GENECODER_SIM_SEED %r, falling back to default RNG",
                seed_env,
            )
            seed = None
    else:
        seed = None

    if _RNG is None or seed != _LAST_SEED:
        _RNG = random.Random(seed) if seed is not None else random.Random()
        _LAST_SEED = seed
    return _RNG


def reset_rng() -> None:
    """Reset the module's global RNG.

    The next call to :func:`make_rng` will reseed from the current
    ``GENECODER_SIM_SEED`` environment variable. This is useful for
    test harnesses that invoke CLI commands multiple times within the
    same process.
    """

    global _RNG, _LAST_SEED
    _RNG = None
    _LAST_SEED = None
