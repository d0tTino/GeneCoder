from __future__ import annotations

"""Backward-compatible facade for legacy pipeline imports."""

import warnings

from .compat.v1.pipeline_adapter import SequencePipeline, core, init_plugins, run_pipeline

__all__ = ["SequencePipeline", "run_pipeline", "core", "init_plugins"]

warnings.warn(
    "genecoder.pipeline is deprecated and will be removed in v0.16.0; "
    "import genecoder.app.RunPipelineUseCase for orchestration.",
    DeprecationWarning,
    stacklevel=2,
)
