from __future__ import annotations

"""Versioned compatibility adapter for deprecated ``genecoder.pipeline`` imports."""

from ... import core
from ...app.pipeline_runtime import SequencePipeline, run_pipeline
from ...plugin_manager import init_plugins

__all__ = ["SequencePipeline", "run_pipeline", "core", "init_plugins"]
