from __future__ import annotations

"""Versioned compatibility adapter for deprecated ``genecoder.api`` imports."""

from genecoder._deprecation import warn_with_telemetry

from ...plugin_api import Codec, FEC, Simulator, Visualizer

__all__ = ["Codec", "FEC", "Simulator", "Visualizer"]

warn_with_telemetry(
    module_name="genecoder.compat.v1.api_adapter",
    message="genecoder.compat.v1.api_adapter is deprecated; import plugin interfaces from genecoder.sdk.plugins.",
    stacklevel=2,
)
