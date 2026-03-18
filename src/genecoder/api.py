from __future__ import annotations

"""Backward-compatible facade for plugin abstract interfaces."""

from ._deprecation import warn_with_telemetry
from .compat.v1.api_adapter import Codec, FEC, Simulator, Visualizer

__all__ = ["Codec", "FEC", "Simulator", "Visualizer"]

warn_with_telemetry(
    module_name="genecoder.api",
    message=(
        "genecoder.api is deprecated and will be removed in v0.16.0; "
        "import plugin interfaces from genecoder.sdk.plugins."
    ),
    stacklevel=2,
)
