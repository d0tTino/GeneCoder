"""Compatibility wrapper for :mod:`genecoder.error_simulation`.

This module is deprecated; use :mod:`genecoder.error_simulation` instead.
"""
from __future__ import annotations

from .error_simulation import (
    simulate_errors,
    apply_substitutions,
    apply_insertions,
    apply_deletions,
    Channel,
    NUCLEOTIDES,
    register,
)

__all__ = [
    "simulate_errors",
    "apply_substitutions",
    "apply_insertions",
    "apply_deletions",
    "Channel",
    "register",
    "NUCLEOTIDES",
]
