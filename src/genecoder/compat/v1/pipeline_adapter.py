from __future__ import annotations

"""Versioned compatibility adapter for deprecated ``genecoder.pipeline`` imports.

Compatibility-only module: do not add new product features here.
"""

from genecoder._deprecation import warn_with_telemetry

from ... import core
from ...app.pipeline_runtime import run_pipeline
from ...compat.legacy.sequence_pipeline import SequencePipeline
from ...plugin_manager import init_plugins

__all__ = ["SequencePipeline", "run_pipeline", "core", "init_plugins"]

warn_with_telemetry(
    module_name="genecoder.compat.v1.pipeline_adapter",
    message="genecoder.compat.v1.pipeline_adapter is deprecated; import orchestration interfaces from genecoder.app.",
    stacklevel=2,
)
