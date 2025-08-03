"""Utility helpers for reproducible randomness."""
from __future__ import annotations

import os
import random
import logging
from typing import Optional

__all__ = ["make_rng"]


logger = logging.getLogger(__name__)


_RNG: Optional[random.Random] = None


def make_rng() -> random.Random:
    """Return a module-wide :class:`~random.Random` seeded once.

    The RNG is seeded from the ``GENECODER_SIM_SEED`` environment variable
    on first invocation and reused for all subsequent calls.  If the
    environment variable is unset or invalid, a default RNG is created.
    """

    global _RNG
    if _RNG is None:
        seed_env = os.getenv("GENECODER_SIM_SEED")
        if seed_env is not None:
            try:
                _RNG = random.Random(int(seed_env))
            except ValueError:
                logger.warning(
                    "Invalid GENECODER_SIM_SEED %r, falling back to default RNG",
                    seed_env,
                )
                _RNG = random.Random()
        else:
            _RNG = random.Random()
    return _RNG
