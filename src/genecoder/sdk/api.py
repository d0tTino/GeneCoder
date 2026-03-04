from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from ..app import (
    ArtifactOutputPolicy,
    BatchSweepMatrix,
    ChannelProfile,
    ConstraintProfile,
    UIService,
    SeedProfile,
    UIRunRequest,
    UIRunResult,
)


from ..profiles.registry import canonicalize_profile_name
SpecInput = "ExperimentRequest | Mapping[str, Any] | str | Path"


@dataclass(frozen=True)
class ExperimentRequest:
    """Stable SDK request contract for one pipeline run."""

    codec: str
    input_path: str
    output_path: str
    fec_backend: str | None = None
    channel: str | None = None
    filter_mutated: bool = False
    profile: ChannelProfile | None = None
    seeds: SeedProfile | None = None
    matrix: BatchSweepMatrix | None = None
    constraints: ConstraintProfile | None = None
    artifacts: ArtifactOutputPolicy = ArtifactOutputPolicy()


@dataclass(frozen=True)
class ExperimentResult:
    """Immutable SDK result payload containing run schema and artifact paths."""

    request: ExperimentRequest
    decoded: bytes
    canonical_run: Mapping[str, Any]
    dashboard_metrics: Mapping[str, Any]
    artifact_paths: Mapping[str, str | None]
    metrics: Mapping[str, Any]
    fec_info: Mapping[str, Any] | None

    @property
    def spec(self) -> ExperimentRequest:
        """Backwards-compatible alias for older SDK integrations."""

        return self.request


@dataclass(frozen=True)
class SweepResult:
    """Immutable grouped results for a parameter sweep."""

    runs: tuple[ExperimentResult, ...]


def _load_yaml_spec(path: Path) -> Mapping[str, Any]:
    loaded = yaml.safe_load(path.read_text())
    if not isinstance(loaded, Mapping):
        raise TypeError(f"Expected mapping at {path}, got {type(loaded)!r}")
    return loaded


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _request_from_mapping(raw: Mapping[str, Any]) -> ExperimentRequest:
    profile_raw = _as_mapping(raw.get("profile"))
    seeds_raw = _as_mapping(raw.get("seeds"))
    matrix_raw = _as_mapping(raw.get("matrix"))
    constraints_raw = _as_mapping(raw.get("constraints"))
    artifacts_raw = _as_mapping(raw.get("artifacts"))

    return ExperimentRequest(
        codec=str(raw["codec"]),
        input_path=str(raw["input_path"]),
        output_path=str(raw["output_path"]),
        fec_backend=(None if raw.get("fec_backend") in (None, "") else str(raw["fec_backend"])),
        channel=(None if raw.get("channel") in (None, "") else str(raw["channel"])),
        filter_mutated=bool(raw.get("filter_mutated", False)),
        profile=(
            ChannelProfile(
                name=str(canonicalize_profile_name(str(profile_raw.get("name"))) or str(profile_raw.get("name"))),
                parameters={str(k): v for k, v in _as_mapping(profile_raw.get("parameters")).items()},
            )
            if profile_raw
            else None
        ),
        seeds=(
            SeedProfile(
                global_seed=seeds_raw.get("global_seed"),
                encode_seed=seeds_raw.get("encode_seed"),
                simulate_seed=seeds_raw.get("simulate_seed"),
                decode_seed=seeds_raw.get("decode_seed"),
            )
            if seeds_raw
            else None
        ),
        matrix=(
            BatchSweepMatrix(
                axes={str(k): tuple(v) if isinstance(v, (list, tuple)) else (v,) for k, v in matrix_raw.items()}
            )
            if matrix_raw
            else None
        ),
        constraints=(
            ConstraintProfile(
                min_length=constraints_raw.get("min_length"),
                max_length=constraints_raw.get("max_length"),
                gc_min=constraints_raw.get("gc_min"),
                gc_max=constraints_raw.get("gc_max"),
                max_homopolymer=constraints_raw.get("max_homopolymer"),
            )
            if constraints_raw
            else None
        ),
        artifacts=ArtifactOutputPolicy(
            metrics_path=(str(artifacts_raw["metrics_path"]) if artifacts_raw.get("metrics_path") else None),
            emit_manifest=bool(artifacts_raw.get("emit_manifest", True)),
            emit_html_report=bool(artifacts_raw.get("emit_html_report", False)),
        ),
    )


def _normalize_request(spec: SpecInput) -> ExperimentRequest:
    if isinstance(spec, ExperimentRequest):
        return spec
    if isinstance(spec, Mapping):
        return _request_from_mapping(spec)
    path = Path(spec)
    return _request_from_mapping(_load_yaml_spec(path))


def _to_result(request: ExperimentRequest, response: UIRunResult) -> ExperimentResult:
    return ExperimentResult(
        request=request,
        decoded=response.decoded,
        canonical_run=dict(response.run_schema),
        dashboard_metrics=dict(response.dashboard_metrics),
        artifact_paths={
            "metrics": response.metrics_path,
            "manifest": response.manifest_path,
            "html_report": response.html_report_path,
        },
        metrics=dict(response.dashboard_metrics),
        fec_info=(dict(response.fec_info) if isinstance(response.fec_info, Mapping) else response.fec_info),
    )


def run_experiment(spec: SpecInput) -> ExperimentResult:
    """Run one experiment from dataclass, mapping, or YAML file path."""

    normalized = _normalize_request(spec)
    response = UIService().run_pipeline_ui(
        UIRunRequest(
            codec=normalized.codec,
            fec=normalized.fec_backend,
            channel=normalized.channel,
            input_path=normalized.input_path,
            output_path=normalized.output_path,
            filter_mutated=normalized.filter_mutated,
            profile=normalized.profile,
            seeds=normalized.seeds,
            matrix=normalized.matrix,
            constraints=normalized.constraints,
            artifacts=normalized.artifacts,
        )
    )
    return _to_result(normalized, response)


def sweep(specs: Iterable[SpecInput]) -> SweepResult:
    """Run a collection of experiments and return immutable results."""

    return SweepResult(tuple(run_experiment(spec) for spec in specs))


__all__ = [
    "ExperimentRequest",
    "ExperimentResult",
    "SweepResult",
    "run_experiment",
    "sweep",
]
