from __future__ import annotations

"""Backward-compatible facade for legacy pipeline imports.

This module also provides the run-scoped KPI bundle contract used by CLI
wrappers and CI gate checks.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import warnings

from .compat.v1.pipeline_adapter import (
    SequencePipeline,
    core,
    init_plugins,
    run_pipeline,
)
from .pipeline_service_contract import (
    AsyncJobMetadata,
    PipelineDryRunResponse,
    PipelineJobRequest,
    bundle_config_to_job_request,
    make_async_job_metadata,
    planned_execution_graph,
)
from .results.schema import (
    canonical_comparison_metrics,
    canonical_metrics_view,
    migrate_run_schema,
)
from .results.repro_report import generate_reproducibility_report

KPI_BUNDLE_VERSION = "1.0"


def build_kpi_bundle(
    run_schema: Mapping[str, Any], *, artifact_path: str | None = None
) -> dict[str, Any]:
    """Return the machine-readable KPI bundle for a canonical run artifact."""

    canonical_run = migrate_run_schema(run_schema)
    run_id = str(canonical_run.get("run_id") or "run")
    metrics_view = canonical_metrics_view(canonical_run)
    comparison = canonical_comparison_metrics(canonical_run)

    bundle: dict[str, Any] = {
        "schema_version": KPI_BUNDLE_VERSION,
        "source": "genecoder.pipeline",
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kpis": {
            "comparison": comparison,
            "dashboard": metrics_view,
        },
    }
    if artifact_path:
        bundle["artifacts"] = {"run_schema": str(Path(artifact_path))}
    return bundle


__all__ = [
    "SequencePipeline",
    "run_pipeline",
    "core",
    "init_plugins",
    "KPI_BUNDLE_VERSION",
    "build_kpi_bundle",
    "generate_reproducibility_report",
    "PipelineJobRequest",
    "PipelineDryRunResponse",
    "AsyncJobMetadata",
    "planned_execution_graph",
    "make_async_job_metadata",
    "bundle_config_to_job_request",
]

warnings.warn(
    "genecoder.pipeline is deprecated and will be removed in v0.16.0; "
    "import genecoder.app.RunPipelineUseCase for orchestration.",
    DeprecationWarning,
    stacklevel=2,
)
