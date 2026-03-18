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


def _require_run_scoped_artifact_path(artifact_path: str) -> str:
    """Return a normalized metrics artifact path and reject home-scoped defaults."""

    raw_path = Path(artifact_path).expanduser()
    home = Path.home()
    try:
        if raw_path.is_absolute() and raw_path.is_relative_to(home):
            raise ValueError(
                "KPI artifacts must use run-scoped paths, not home-directory state."
            )
    except AttributeError:
        raw_parts = raw_path.parts
        home_parts = home.parts
        if len(raw_parts) >= len(home_parts) and raw_parts[: len(home_parts)] == home_parts:
            raise ValueError(
                "KPI artifacts must use run-scoped paths, not home-directory state."
            )

    if raw_path.name != "metrics.json":
        raise ValueError(
            "KPI bundle artifact_path must point to a run-scoped metrics.json file."
        )
    return str(raw_path)


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
        bundle["artifacts"] = {
            "run_schema": _require_run_scoped_artifact_path(artifact_path)
        }
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
