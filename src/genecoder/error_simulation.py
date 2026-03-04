"""Deprecated compatibility shim for legacy error simulation imports."""
from __future__ import annotations

import warnings

warnings.warn(
    "genecoder.error_simulation is deprecated and will be removed in v0.15.0; "
    "use genecoder.app.RunPipelineUseCase and genecoder.simulators instead.",
    DeprecationWarning,
    stacklevel=2,
)

from .compat.error_simulation import *  # noqa: F403
