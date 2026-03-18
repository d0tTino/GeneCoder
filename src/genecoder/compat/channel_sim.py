"""Compatibility wrapper for legacy channel simulation imports.

Compatibility-only module: do not add new feature logic.
"""
from __future__ import annotations

from genecoder._deprecation import warn_with_telemetry

from genecoder.compat.legacy.channel_adapter_exports import *  # noqa: F403

warn_with_telemetry(
    module_name="genecoder.compat.channel_sim",
    message="genecoder.compat.channel_sim is deprecated; import channel functionality from genecoder.channel_engine or supported app/sdk entrypoints.",
    stacklevel=2,
)
