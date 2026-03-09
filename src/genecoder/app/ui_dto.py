from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class UIConstraintLimits:
    gc_min: float = 0.4
    gc_max: float = 0.6
    max_homopolymer: int = 8


@dataclass(frozen=True)
class UIPresentationPayload:
    """Canonical UI payload used by all presentation adapters.

    This DTO normalizes metric-derived fields that multiple frontends render,
    so adapters (Flet/Streamlit/React) consume identical data semantics.
    """

    metrics: Mapping[str, Any]
    constraint_limits: UIConstraintLimits
    oligo_records: tuple[Mapping[str, Any], ...]

    @classmethod
    def from_metrics(cls, metrics: Mapping[str, Any]) -> "UIPresentationPayload":
        limits = _constraint_limits(metrics)
        records = _extract_oligo_records(metrics)
        return cls(
            metrics=dict(metrics),
            constraint_limits=limits,
            oligo_records=tuple(records),
        )

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


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(int(value))
    if isinstance(value, str):
        norm = value.strip().lower()
        if norm in {"1", "true", "yes", "on"}:
            return True
    return False


def _constraint_limits(metrics: Mapping[str, Any]) -> UIConstraintLimits:
    gc_min = 0.4
    gc_max = 0.6
    max_hp = 8
    violations = metrics.get("constraint_violations")
    if isinstance(violations, Mapping):
        limits = violations.get("limits")
        if isinstance(limits, Mapping):
            gc_min_val = limits.get("gc_min")
            gc_max_val = limits.get("gc_max")
            max_hp_val = limits.get("max_homopolymer")
            if isinstance(gc_min_val, (int, float)) and not isinstance(gc_min_val, bool):
                gc_min = float(gc_min_val)
            if isinstance(gc_max_val, (int, float)) and not isinstance(gc_max_val, bool):
                gc_max = float(gc_max_val)
            if isinstance(max_hp_val, (int, float)) and not isinstance(max_hp_val, bool):
                max_hp = int(max_hp_val)
    return UIConstraintLimits(gc_min=gc_min, gc_max=gc_max, max_homopolymer=max_hp)


def _extract_oligo_records(metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    oligo = metrics.get("oligo_metrics")
    if not isinstance(oligo, Mapping):
        return []
    gc_vals = [float(v) for v in oligo.get("gc_percentages", []) if isinstance(v, (int, float))]
    hp_vals = [float(v) for v in oligo.get("max_homopolymers", []) if isinstance(v, (int, float))]
    dropout_flags = [_parse_bool(v) for v in oligo.get("dropout_flags", [])]

    ecc_map: dict[str, list[float]] = {}
    ecc = oligo.get("ecc_success")
    if isinstance(ecc, Mapping):
        for name, values in ecc.items():
            if isinstance(values, list):
                filtered = [float(v) for v in values if isinstance(v, (int, float, bool))]
                if filtered:
                    ecc_map[str(name)] = [float(v) if not isinstance(v, bool) else (1.0 if v else 0.0) for v in filtered]

    base_lengths = [len(gc_vals), len(hp_vals), len(dropout_flags)]
    max_len = max(base_lengths + [len(v) for v in ecc_map.values()]) if (base_lengths or ecc_map) else 0
    if max_len == 0:
        return []

    records: list[dict[str, Any]] = []
    for idx in range(max_len):
        record: dict[str, Any] = {"Index": idx + 1}
        if idx < len(gc_vals):
            record["GC%"] = gc_vals[idx]
        if idx < len(hp_vals):
            record["Max Homopolymer"] = hp_vals[idx]
        if idx < len(dropout_flags):
            record["Dropout"] = dropout_flags[idx]
        for name, values in ecc_map.items():
            if idx < len(values):
                record[f"ECC:{name}"] = values[idx]
        records.append(record)
    return records
