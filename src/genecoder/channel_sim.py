"""Compatibility wrapper for :mod:`genecoder.error_simulation`.

This module is deprecated; use :mod:`genecoder.error_simulation` instead.
"""
from __future__ import annotations

import random
import warnings

from .error_simulation import (
    apply_substitutions,
    apply_insertions,
    apply_deletions,
    Channel,
    NUCLEOTIDES,
    register,
    simulate_errors as _simulate_errors,
)

__all__ = [
    "apply_substitutions",
    "apply_insertions",
    "apply_deletions",
    "Channel",
    "register",
    "NUCLEOTIDES",
]


def simulate_errors(
    sequence: str,
    substitution_prob: float = 0.0,
    insertion_prob: float = 0.0,
    deletion_prob: float = 0.0,
    rng: random.Random | None = None,
) -> str:
    """Introduce substitutions, insertions and deletions into ``sequence``.

    This wrapper mirrors :func:`genecoder.error_simulation.simulate_errors` while
    keeping the legacy module path. All parameters are forwarded to the new
    implementation.

    Parameters
    ----------
    sequence:
        Input DNA sequence.
    substitution_prob, insertion_prob, deletion_prob:
        Probabilities for each error type. Their sum must not exceed ``1``.
    rng:
        Optional random number generator for deterministic behaviour.
    """

    warnings.warn(
        "genecoder.channel_sim is deprecated; import genecoder.channel_engine or genecoder.error_simulation instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return _simulate_errors(
        sequence,
        substitution_prob=substitution_prob,
        insertion_prob=insertion_prob,
        deletion_prob=deletion_prob,
        rng=rng,
    )


__all__.append("simulate_errors")
