"""Shared legacy channel/error simulation re-exports.

Compatibility-only module: no new feature work.
"""

from __future__ import annotations

from genecoder._deprecation import warn_with_telemetry

from genecoder.channel_engine.legacy_adapter import (
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

warn_with_telemetry(
    module_name="genecoder.compat.legacy.channel_adapter_exports",
    message="genecoder.compat.legacy.channel_adapter_exports is deprecated; use supported channel_engine or app/sdk interfaces instead.",
    stacklevel=2,
)
