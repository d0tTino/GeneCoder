from __future__ import annotations

"""Removed compatibility module kept as an import-time deprecation stub."""

from genecoder._deprecation import warn_with_telemetry

__all__: list[str] = []

warn_with_telemetry(
    module_name="genecoder.compat.legacy.sequence_pipeline",
    message=(
        "genecoder.compat.legacy.sequence_pipeline was removed in v0.17.0; "
        "use genecoder.app.RunPipelineUseCase for public orchestration."
    ),
    stacklevel=2,
)
