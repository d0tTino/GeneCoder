from __future__ import annotations

"""Service-facing stateless contract for pipeline job execution."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import uuid

from genecoder.app import (
    ArtifactOutputPolicy,
    BatchSweepMatrix,
    ChannelProfile,
    ConstraintProfile,
    RunPipelineRequest,
    SeedProfile,
)


@dataclass(frozen=True)
class AsyncJobMetadata:
    """Async metadata envelope for future queue-backed execution."""

    job_id: str
    status: str
    submitted_at: str
    mode: str = "local-inline"


@dataclass(frozen=True)
class PipelineJobRequest:
    codec: str
    input_path: str
    output_path: str
    fec: str | None = None
    channel: str | None = None
    filter_mutated: bool = False
    profile_name: str | None = None
    profile_parameters: Mapping[str, Any] = field(default_factory=dict)
    seeds: Mapping[str, int | None] = field(default_factory=dict)
    matrix_axes: Mapping[str, tuple[Any, ...]] = field(default_factory=dict)
    constraints: Mapping[str, Any] = field(default_factory=dict)
    artifacts: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "PipelineJobRequest":
        codec = str(payload.get("codec") or "").strip()
        input_path = str(payload.get("input_path") or "").strip()
        output_path = str(payload.get("output_path") or "").strip()
        if not codec:
            raise ValueError("codec is required")
        if not input_path:
            raise ValueError("input_path is required")
        if not output_path:
            raise ValueError("output_path is required")

        profile_parameters = payload.get("profile_parameters")
        if not isinstance(profile_parameters, Mapping):
            profile_parameters = {}
        seeds = payload.get("seeds")
        if not isinstance(seeds, Mapping):
            seeds = {}
        matrix_axes = payload.get("matrix_axes")
        if not isinstance(matrix_axes, Mapping):
            matrix_axes = {}
        constraints = payload.get("constraints")
        if not isinstance(constraints, Mapping):
            constraints = {}
        artifacts = payload.get("artifacts")
        if not isinstance(artifacts, Mapping):
            artifacts = {}

        return cls(
            codec=codec,
            input_path=input_path,
            output_path=output_path,
            fec=str(payload["fec"]) if payload.get("fec") else None,
            channel=str(payload["channel"]) if payload.get("channel") else None,
            filter_mutated=bool(payload.get("filter_mutated", False)),
            profile_name=(str(payload.get("profile_name") or "").strip() or None),
            profile_parameters=dict(profile_parameters),
            seeds={str(key): value for key, value in seeds.items()},
            matrix_axes={
                str(key): tuple(value) if isinstance(value, (list, tuple)) else (value,)
                for key, value in matrix_axes.items()
            },
            constraints=dict(constraints),
            artifacts=dict(artifacts),
        )

    def to_use_case_request(self) -> RunPipelineRequest:
        profile = (
            ChannelProfile(
                name=self.profile_name,
                parameters=dict(self.profile_parameters),
            )
            if self.profile_name
            else None
        )
        return RunPipelineRequest(
            codec=self.codec,
            input_path=self.input_path,
            output_path=self.output_path,
            fec=self.fec,
            channel=self.channel,
            filter_mutated=self.filter_mutated,
            profile=profile,
            seeds=SeedProfile(
                global_seed=_to_optional_int(self.seeds.get("global_seed")),
                encode_seed=_to_optional_int(self.seeds.get("encode_seed")),
                simulate_seed=_to_optional_int(self.seeds.get("simulate_seed")),
                decode_seed=_to_optional_int(self.seeds.get("decode_seed")),
            ),
            matrix=BatchSweepMatrix(axes=dict(self.matrix_axes)),
            constraints=ConstraintProfile(
                min_length=_to_optional_int(self.constraints.get("min_length")),
                max_length=_to_optional_int(self.constraints.get("max_length")),
                gc_min=_to_optional_float(self.constraints.get("gc_min")),
                gc_max=_to_optional_float(self.constraints.get("gc_max")),
                max_homopolymer=_to_optional_int(
                    self.constraints.get("max_homopolymer")
                ),
            ),
            artifacts=ArtifactOutputPolicy(
                metrics_path=_to_optional_str(self.artifacts.get("metrics_path")),
                emit_manifest=bool(self.artifacts.get("emit_manifest", True)),
                emit_html_report=bool(self.artifacts.get("emit_html_report", False)),
            ),
        )


@dataclass(frozen=True)
class PipelineDryRunResponse:
    metadata: AsyncJobMetadata
    request: PipelineJobRequest
    execution_graph: Mapping[str, Any]


def make_async_job_metadata(status: str) -> AsyncJobMetadata:
    return AsyncJobMetadata(
        job_id=uuid.uuid4().hex,
        status=status,
        submitted_at=datetime.now(timezone.utc).isoformat(),
    )


def planned_execution_graph(request: PipelineJobRequest) -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "encode", "kind": "stage", "codec": request.codec},
            {
                "id": "simulate",
                "kind": "stage",
                "channel": request.channel,
                "profile": request.profile_name,
            },
            {"id": "decode", "kind": "stage", "codec": request.codec},
            {
                "id": "artifacts",
                "kind": "sink",
                "metrics_path": request.artifacts.get("metrics_path"),
                "output_path": request.output_path,
            },
        ],
        "edges": [
            {"from": "encode", "to": "simulate"},
            {"from": "simulate", "to": "decode"},
            {"from": "decode", "to": "artifacts"},
        ],
    }


def bundle_config_to_job_request(
    bundle_config: Mapping[str, Any],
    *,
    input_path: str,
    output_path: str,
) -> PipelineJobRequest:
    encode_cfg = bundle_config.get("encode")
    simulate_cfg = bundle_config.get("simulate")

    if not isinstance(encode_cfg, Mapping):
        raise ValueError("bundle encode section must be a mapping")

    codec = str(encode_cfg.get("method") or "base4_direct")
    fec = _resolve_fec(encode_cfg)

    channel: str | None = None
    profile_name: str | None = None
    profile_parameters: dict[str, Any] = {}
    constraints: dict[str, Any] = {}

    if isinstance(simulate_cfg, Mapping):
        simulators = simulate_cfg.get("simulators")
        if isinstance(simulators, list) and simulators:
            candidate = simulators[0]
            if isinstance(candidate, Mapping):
                channel = str(candidate.get("name") or "") or None
                profile_name = str(candidate.get("profile") or "") or None
                profile_parameters = {
                    str(k): v
                    for k, v in candidate.items()
                    if k not in {"name", "profile"}
                }
            elif isinstance(candidate, str):
                channel = candidate

        synthesis_cfg = simulate_cfg.get("synthesis")
        if isinstance(synthesis_cfg, Mapping):
            constraints = {
                key: synthesis_cfg.get(key)
                for key in (
                    "min_length",
                    "max_length",
                    "gc_min",
                    "gc_max",
                    "max_homopolymer",
                )
                if key in synthesis_cfg
            }

    return PipelineJobRequest(
        codec=codec,
        input_path=str(Path(input_path)),
        output_path=str(Path(output_path)),
        fec=fec,
        channel=channel,
        profile_name=profile_name,
        profile_parameters=profile_parameters,
        constraints=constraints,
    )


def _resolve_fec(encode_cfg: Mapping[str, Any]) -> str | None:
    fec = encode_cfg.get("fec")
    if isinstance(fec, str) and fec:
        return fec
    layers = encode_cfg.get("layers")
    if isinstance(layers, list):
        for layer in layers:
            if not isinstance(layer, Mapping):
                continue
            if str(layer.get("type", "")).lower() == "fec":
                name = layer.get("name")
                if isinstance(name, str) and name:
                    return name
    return None


def _to_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_optional_str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None
