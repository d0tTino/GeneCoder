"""Compatibility wrapper for legacy channel simulation imports."""
from __future__ import annotations

from genecoder.compat.error_simulation import (
    ADAPTER_PROFILES,
    DEFAULT_ADAPTER_PROFILE,
    INDEL_PROFILES,
    NUCLEOTIDES,
    Channel,
    apply_deletions,
    apply_insertions,
    apply_substitutions,
    register,
    simulate_errors,
)

__all__ = [
    "apply_substitutions",
    "apply_insertions",
    "apply_deletions",
    "Channel",
    "register",
    "NUCLEOTIDES",
    "simulate_errors",
    "INDEL_PROFILES",
    "ADAPTER_PROFILES",
    "DEFAULT_ADAPTER_PROFILE",
]
