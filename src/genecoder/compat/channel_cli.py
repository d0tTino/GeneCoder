from __future__ import annotations

"""Removed compatibility module kept as an import-time deprecation stub."""

from genecoder._deprecation import warn_with_telemetry

__all__: list[str] = []

warn_with_telemetry(
    module_name="genecoder.compat.channel_cli",
    message=(
        "genecoder.compat.channel_cli was removed in v0.17.0; import indel profile helpers from genecoder.core."
    ),
    stacklevel=2,
)
