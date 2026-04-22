from __future__ import annotations

"""Versioned compatibility adapter for deprecated ``genecoder.pipeline`` imports.

Compatibility-only module: do not add new product features here.
"""

from genecoder._deprecation import warn_with_telemetry

from ... import core
from ...app.pipeline_use_case import RunPipelineRequest, RunPipelineUseCase
from ...app.sequence_pipeline import SequencePipeline
from ...plugin_manager import init_plugins


def run_pipeline(
    codec: str,
    fec_backend: str | None,
    channel: str | None,
    input_path: str,
    output_path: str,
    filter_mutated: bool = False,
):
    """Compatibility wrapper routing orchestration through RunPipelineUseCase."""

    response = RunPipelineUseCase().execute(
        RunPipelineRequest(
            codec=codec,
            input_path=input_path,
            output_path=output_path,
            fec=fec_backend,
            channel=channel,
            filter_mutated=filter_mutated,
        )
    )
    outcome = response.run_schema.get("outcome", {})
    metrics = outcome.get("metrics", {}) if isinstance(outcome, dict) else {}
    return response.decoded, dict(metrics), response.fec_info


__all__ = ["SequencePipeline", "run_pipeline", "core", "init_plugins"]

warn_with_telemetry(
    module_name="genecoder.compat.v1.pipeline_adapter",
    message="genecoder.compat.v1.pipeline_adapter is deprecated; import orchestration interfaces from genecoder.app.",
    stacklevel=2,
)
