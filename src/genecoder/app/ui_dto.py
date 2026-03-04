from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .pipeline_use_case import (
    ArtifactOutputPolicy,
    BatchSweepMatrix,
    ChannelProfile,
    ConstraintProfile,
    RunPipelineRequest,
    RunPipelineResponse,
    SeedProfile,
)


@dataclass(frozen=True)
class UIRunRequest:
    codec: str
    input_path: str
    output_path: str
    fec: str | None = None
    channel: str | None = None
    filter_mutated: bool = False
    profile: ChannelProfile | None = None
    seeds: SeedProfile | None = None
    matrix: BatchSweepMatrix | None = None
    constraints: ConstraintProfile | None = None
    artifacts: ArtifactOutputPolicy = ArtifactOutputPolicy()

    def to_use_case_request(self) -> RunPipelineRequest:
        return RunPipelineRequest(
            codec=self.codec,
            input_path=self.input_path,
            output_path=self.output_path,
            fec=self.fec,
            channel=self.channel,
            filter_mutated=self.filter_mutated,
            profile=self.profile,
            seeds=self.seeds,
            matrix=self.matrix,
            constraints=self.constraints,
            artifacts=self.artifacts,
        )


@dataclass(frozen=True)
class UIRunResult:
    decoded: bytes
    dashboard_metrics: Mapping[str, Any]
    run_schema: Mapping[str, Any]
    metrics_path: str
    manifest_path: str | None
    html_report_path: str | None
    fec_info: Mapping[str, Any] | None

    @classmethod
    def from_use_case_response(cls, response: RunPipelineResponse) -> "UIRunResult":
        return cls(
            decoded=response.decoded,
            dashboard_metrics=dict(response.dashboard_metrics),
            run_schema=dict(response.run_schema),
            metrics_path=response.metrics_path,
            manifest_path=response.manifest_path,
            html_report_path=response.html_report_path,
            fec_info=(dict(response.fec_info) if isinstance(response.fec_info, Mapping) else response.fec_info),
        )


@dataclass(frozen=True)
class UIMetricsSummary:
    decode_success_rate: float | None
    gc_content: float | None
    max_homopolymer: float | None
    constraint_violations: int

    @classmethod
    def from_metrics(cls, metrics: Mapping[str, Any]) -> "UIMetricsSummary":
        violations = metrics.get("constraint_violations")
        violation_count = int(violations) if isinstance(violations, (int, float)) else 0
        return cls(
            decode_success_rate=(
                float(metrics["decode_success_rate"])
                if isinstance(metrics.get("decode_success_rate"), (int, float))
                else None
            ),
            gc_content=float(metrics["gc_content"]) if isinstance(metrics.get("gc_content"), (int, float)) else None,
            max_homopolymer=(
                float(metrics["max_homopolymer"])
                if isinstance(metrics.get("max_homopolymer"), (int, float))
                else None
            ),
            constraint_violations=violation_count,
        )
