from __future__ import annotations

"""Compatibility adapter for legacy channel CLI helpers."""

from genecoder._deprecation import warn_with_telemetry

from genecoder.core import (
    LEGACY_DEFAULT_INDEL_PROFILE,
    LEGACY_INDEL_PROFILE_ALIASES,
    LEGACY_INDEL_PROFILE_NAMES,
    MODERN_INDEL_PROFILES,
    resolve_indel_profile,
)

__all__ = [
    "MODERN_INDEL_PROFILES",
    "LEGACY_INDEL_PROFILE_ALIASES",
    "LEGACY_INDEL_PROFILE_NAMES",
    "LEGACY_DEFAULT_INDEL_PROFILE",
    "resolve_indel_profile",
]

warn_with_telemetry(
    module_name="genecoder.compat.channel_cli",
    message="genecoder.compat.channel_cli is deprecated; import indel profile helpers from genecoder.core.",
    stacklevel=2,
)
