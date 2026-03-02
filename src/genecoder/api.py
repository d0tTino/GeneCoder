from __future__ import annotations

"""Backward-compatible facade for plugin abstract interfaces."""

import warnings

from .compat.v1.api_adapter import Codec, FEC, Simulator, Visualizer

__all__ = ["Codec", "FEC", "Simulator", "Visualizer"]

warnings.warn(
    "genecoder.api is deprecated and will be removed in v0.16.0; "
    "import plugin interfaces from genecoder.sdk.plugins.",
    DeprecationWarning,
    stacklevel=2,
)
