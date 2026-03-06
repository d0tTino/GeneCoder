from __future__ import annotations

"""Compatibility adapter for legacy channel CLI helpers."""

import warnings

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

warnings.warn(
    "genecoder.compat.channel_cli is deprecated; import indel profile helpers from genecoder.core.",
    DeprecationWarning,
    stacklevel=2,
)
