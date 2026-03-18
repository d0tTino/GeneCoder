"""Compatibility wrapper for legacy error simulation imports.

Compatibility-only module: do not add new feature logic.
"""
from __future__ import annotations

from genecoder._deprecation import warn_with_telemetry

from genecoder.compat.legacy.channel_adapter_exports import *  # noqa: F403

warn_with_telemetry(
    module_name="genecoder.compat.error_simulation",
    message="genecoder.compat.error_simulation is deprecated; import channel functionality from genecoder.channel_engine or supported app/sdk entrypoints.",
    stacklevel=2,
)
