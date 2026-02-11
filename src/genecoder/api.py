from __future__ import annotations

"""Backward-compatible facade for plugin abstract interfaces."""

import warnings

from .plugin_api import Codec, FEC, Simulator, Visualizer

__all__ = ["Codec", "FEC", "Simulator", "Visualizer"]

warnings.warn(
    "genecoder.api is deprecated and will be removed in a future release; "
    "import plugin interfaces from genecoder.plugin_api instead.",
    DeprecationWarning,
    stacklevel=2,
)
