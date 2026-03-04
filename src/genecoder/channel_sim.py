"""Deprecated compatibility shim for legacy channel simulation imports."""
from __future__ import annotations

import warnings

warnings.warn(
    "genecoder.channel_sim is deprecated and will be removed in v0.15.0; "
    "use genecoder.app.RunPipelineUseCase and genecoder.simulators instead.",
    DeprecationWarning,
    stacklevel=2,
)

from .compat.channel_sim import *  # noqa: F403
