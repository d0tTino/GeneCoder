from __future__ import annotations

"""Backward-compatible facade for legacy pipeline imports."""

import warnings

from . import core
from .app.pipeline_runtime import SequencePipeline, run_pipeline

__all__ = ["SequencePipeline", "run_pipeline", "core"]

warnings.warn(
    "genecoder.pipeline is deprecated and will be removed in a future release; "
    "import pipeline runtime/use-case helpers from genecoder.app instead.",
    DeprecationWarning,
    stacklevel=2,
)
