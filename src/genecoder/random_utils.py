"""Utility helpers for reproducible randomness."""
from __future__ import annotations

import os
import random

__all__ = ["make_rng"]


def make_rng() -> random.Random:
    """Return a :class:`~random.Random` seeded from ``GENECODER_SIM_SEED``."""
    seed_env = os.getenv("GENECODER_SIM_SEED")
    return random.Random(int(seed_env)) if seed_env is not None else random.Random()
