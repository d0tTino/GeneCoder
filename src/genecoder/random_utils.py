"""Utility helpers for reproducible randomness."""
from __future__ import annotations

import os
import random
import logging

__all__ = ["make_rng"]


logger = logging.getLogger(__name__)


def make_rng() -> random.Random:
    """Return a :class:`~random.Random` seeded from ``GENECODER_SIM_SEED``."""
    seed_env = os.getenv("GENECODER_SIM_SEED")
    if seed_env is not None:
        try:
            return random.Random(int(seed_env))
        except ValueError:
            logger.warning(
                "Invalid GENECODER_SIM_SEED %r, falling back to default RNG",
                seed_env,
            )
    return random.Random()
