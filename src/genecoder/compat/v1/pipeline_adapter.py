from __future__ import annotations

"""Versioned compatibility adapter for deprecated ``genecoder.pipeline`` imports.

Compatibility-only module: do not add new product features here.
"""

from ... import core
from ...app.pipeline_runtime import run_pipeline
from ...compat.legacy.sequence_pipeline import SequencePipeline
from ...plugin_manager import init_plugins

__all__ = ["SequencePipeline", "run_pipeline", "core", "init_plugins"]
