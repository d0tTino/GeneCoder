from __future__ import annotations

"""Compatibility shim for deprecated ``SequencePipeline`` import path."""

from genecoder._deprecation import warn_with_telemetry

from genecoder.app.sequence_pipeline import SequencePipeline

__all__ = ["SequencePipeline"]

warn_with_telemetry(
    module_name="genecoder.compat.legacy.sequence_pipeline",
    message="genecoder.compat.legacy.sequence_pipeline is deprecated; import SequencePipeline from genecoder.app.sequence_pipeline.",
    stacklevel=2,
)
