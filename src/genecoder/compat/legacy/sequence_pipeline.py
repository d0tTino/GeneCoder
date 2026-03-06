from __future__ import annotations

"""Compatibility shim for deprecated ``SequencePipeline`` import path."""

import warnings

from genecoder.app.sequence_pipeline import SequencePipeline

__all__ = ["SequencePipeline"]

warnings.warn(
    "genecoder.compat.legacy.sequence_pipeline is deprecated; import SequencePipeline from genecoder.app.sequence_pipeline.",
    DeprecationWarning,
    stacklevel=2,
)
