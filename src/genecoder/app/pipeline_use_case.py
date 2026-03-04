from __future__ import annotations

"""Authoritative application orchestration entrypoint.

`RunPipelineUseCase` is the canonical public orchestration API for GeneCoder
runtime execution. Internally it delegates to `genecoder.core.run_canonical_pipeline`
via `genecoder.app.pipeline_runtime.run_pipeline`, which returns metrics derived
from the canonical runtime model (`genecoder.core.CanonicalRuntimeResult`).
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Mapping

from genecoder.manifest import generate_manifest
from .pipeline_runtime import run_pipeline
from genecoder.results.schema import RUN_SCHEMA_VERSION, canonical_metrics_view
from genecoder.html_report import generate_html_report
from genecoder.runtime import make_run_context
from genecoder.profiles.registry import canonicalize_profile_name


@dataclass(frozen=True)
class ChannelProfile:
    name: str
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SeedProfile:
    global_seed: int | None = None
    encode_seed: int | None = None
    simulate_seed: int | None = None
    decode_seed: int | None = None


@dataclass(frozen=True)
class BatchSweepMatrix:
    axes: Mapping[str, tuple[Any, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class ConstraintProfile:
    min_length: int | None = None
    max_length: int | None = None
    gc_min: float | None = None
    gc_max: float | None = None
    max_homopolymer: int | None = None


@dataclass(frozen=True)
class ArtifactOutputPolicy:
    metrics_path: str | None = None
    emit_manifest: bool = True
    emit_html_report: bool = False


@dataclass(frozen=True)
class RunPipelineRequest:
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
    artifacts: ArtifactOutputPolicy = field(default_factory=ArtifactOutputPolicy)


@dataclass(frozen=True)
class RunPipelineResponse:
    decoded: bytes
    dashboard_metrics: Mapping[str, Any]
    run_schema: Mapping[str, Any]
    fec_info: Mapping[str, Any] | None
    metrics_path: str
    manifest_path: str | None
    html_report_path: str | None


class RunPipelineUseCase:
    """Execute the canonical encode/simulate/decode orchestration flow."""

    def execute(self, request: RunPipelineRequest) -> RunPipelineResponse:
        run_context = make_run_context(
            global_seed=request.seeds.global_seed if request.seeds else None,
            encode_seed=request.seeds.encode_seed if request.seeds else None,
            simulate_seed=request.seeds.simulate_seed if request.seeds else None,
            decode_seed=request.seeds.decode_seed if request.seeds else None,
        )
        resolved_profile_name = (
            canonicalize_profile_name(request.profile.name) if request.profile else None
        )
        resolved_channel_name = canonicalize_profile_name(request.channel)

        decoded, metrics, fec_info = run_pipeline(
            codec=request.codec,
            fec_backend=request.fec,
            channel=resolved_channel_name,
            input_path=request.input_path,
            output_path=request.output_path,
            filter_mutated=request.filter_mutated,
            run_context=run_context,
        )

        metrics_path = Path(request.artifacts.metrics_path or str(request.output_path) + ".json")
        run_schema: dict[str, Any] = {
            "schema_version": RUN_SCHEMA_VERSION,
            "source_format": "pipeline_use_case",
            "run_id": Path(request.output_path).stem,
            "profiles": {
                "encoding": request.codec,
                "simulation": resolved_profile_name if resolved_profile_name else resolved_channel_name,
                "decode": request.codec,
            },
            "seeds": {
                "global": run_context.global_seed,
                "encode": run_context.encode_seed,
                "simulate": run_context.simulate_seed,
                "decode": run_context.decode_seed,
                "provenance": run_context.seed_provenance(),
            },
            "runtime": {
                "total_seconds": None,
                "encode_seconds": None,
                "simulate_seconds": None,
                "decode_seconds": None,
            },
            "stages": {
                "encode": {
                    "parameters": {"codec": request.codec, "fec": request.fec},
                    "metrics": {
                        "gc_content": metrics.get("gc_content"),
                        "gc_variance": metrics.get("gc_variance"),
                        "max_homopolymer": metrics.get("max_homopolymer"),
                    },
                },
                "simulate": {
                    "profile": resolved_profile_name if resolved_profile_name else resolved_channel_name,
                    "metrics": {
                        "substitutions": metrics.get("substitutions"),
                        "insertions": metrics.get("insertions"),
                        "deletions": metrics.get("deletions"),
                        "coverage": metrics.get("coverage"),
                        "dropout_count": metrics.get("dropout_count"),
                        "dropout_fraction": metrics.get("dropout_fraction"),
                    },
                },
                "decode": {
                    "parameters": {"codec": request.codec, "fec": request.fec},
                    "metrics": {
                        "decode_success": metrics.get("decode_success"),
                        "decode_success_rate": metrics.get("decode_success_rate"),
                        "ecc_success_rates": metrics.get("ecc_success_rates", {}),
                    },
                },
            },
            "sweep": dict(request.matrix.axes) if request.matrix else {},
            "constraints": (
                {
                    "min_length": request.constraints.min_length,
                    "max_length": request.constraints.max_length,
                    "gc_min": request.constraints.gc_min,
                    "gc_max": request.constraints.gc_max,
                    "max_homopolymer": request.constraints.max_homopolymer,
                }
                if request.constraints
                else {}
            ),
            "input_config": {
                "codec": request.codec,
                "fec": request.fec,
                "channel": resolved_channel_name,
                "channel_profile": (
                    {
                        "name": resolved_profile_name or request.profile.name,
                        "parameters": dict(request.profile.parameters),
                    }
                    if request.profile
                    else None
                ),
            },
            "outcome": {
                "metrics": dict(metrics),
                "fec_info": dict(fec_info) if isinstance(fec_info, Mapping) else fec_info,
            },
            "constraint_outcomes": {
                "summary": metrics.get("constraint_violations"),
                "by_oligo": {},
            },
            "decode_outcomes": {
                "decode_success": metrics.get("decode_success"),
                "decode_success_rate": metrics.get("decode_success_rate"),
                "ecc_success_rates": metrics.get("ecc_success_rates", {}),
            },
            "provenance": {
                "source_format": "pipeline_use_case",
                "generator": "RunPipelineUseCase",
            },
        }
        dashboard_metrics = canonical_metrics_view(run_schema)
        run_schema["dashboard_metrics"] = dashboard_metrics

        metrics_path.write_text(json.dumps(run_schema, indent=2), encoding="utf-8")

        manifest_path: str | None = None
        if request.artifacts.emit_manifest:
            manifest = generate_manifest(
                request.input_path,
                {"method": request.codec, "fec": request.fec, "channel": resolved_channel_name, "seeds": run_context.seed_provenance()},
                dashboard_metrics,
            )
            manifest_file = metrics_path.with_suffix(".manifest.json")
            manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            manifest_path = str(manifest_file)

        html_report_path: str | None = None
        if request.artifacts.emit_html_report and manifest_path:
            report_path = metrics_path.with_suffix(".html")
            report_path.write_text(generate_html_report(manifest_path), encoding="utf-8")
            html_report_path = str(report_path)

        return RunPipelineResponse(
            decoded=decoded,
            dashboard_metrics=dashboard_metrics,
            run_schema=run_schema,
            fec_info=dict(fec_info) if isinstance(fec_info, Mapping) else None,
            metrics_path=str(metrics_path),
            manifest_path=manifest_path,
            html_report_path=html_report_path,
        )
