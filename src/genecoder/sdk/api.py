from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from ..pipeline import run_pipeline

SpecInput = "ExperimentSpec | Mapping[str, Any] | str | Path"


@dataclass(frozen=True)
class ExperimentSpec:
    """SDK specification for a single encode/simulate/decode experiment."""

    codec: str
    input_path: str
    output_path: str
    fec_backend: str | None = None
    channel: str | None = None
    filter_mutated: bool = False


@dataclass(frozen=True)
class ExperimentResult:
    """Immutable normalized result of a single experiment."""

    spec: ExperimentSpec
    decoded: bytes
    metrics: Mapping[str, Any]
    fec_info: Mapping[str, Any] | None


@dataclass(frozen=True)
class SweepResult:
    """Immutable grouped results for a parameter sweep."""

    runs: tuple[ExperimentResult, ...]


def _load_yaml_spec(path: Path) -> Mapping[str, Any]:
    loaded = yaml.safe_load(path.read_text())
    if not isinstance(loaded, Mapping):
        raise TypeError(f"Expected mapping at {path}, got {type(loaded)!r}")
    return loaded


def _spec_from_mapping(raw: Mapping[str, Any]) -> ExperimentSpec:
    return ExperimentSpec(
        codec=str(raw["codec"]),
        input_path=str(raw["input_path"]),
        output_path=str(raw["output_path"]),
        fec_backend=(None if raw.get("fec_backend") in (None, "") else str(raw["fec_backend"])),
        channel=(None if raw.get("channel") in (None, "") else str(raw["channel"])),
        filter_mutated=bool(raw.get("filter_mutated", False)),
    )


def _normalize_spec(spec: ExperimentSpec | Mapping[str, Any] | str | Path) -> ExperimentSpec:
    if isinstance(spec, ExperimentSpec):
        return spec
    if isinstance(spec, Mapping):
        return _spec_from_mapping(spec)
    path = Path(spec)
    return _spec_from_mapping(_load_yaml_spec(path))


def run_experiment(spec: ExperimentSpec | Mapping[str, Any] | str | Path) -> ExperimentResult:
    """Run one experiment from dataclass, mapping, or YAML file path."""

    normalized = _normalize_spec(spec)
    decoded, metrics, fec_info = run_pipeline(
        codec=normalized.codec,
        fec_backend=normalized.fec_backend,
        channel=normalized.channel,
        input_path=normalized.input_path,
        output_path=normalized.output_path,
        filter_mutated=normalized.filter_mutated,
    )
    return ExperimentResult(
        spec=normalized,
        decoded=decoded,
        metrics=dict(metrics),
        fec_info=(dict(fec_info) if isinstance(fec_info, Mapping) else fec_info),
    )


def sweep(specs: Iterable[ExperimentSpec | Mapping[str, Any] | str | Path]) -> SweepResult:
    """Run a collection of experiments and return immutable results."""

    return SweepResult(tuple(run_experiment(spec) for spec in specs))


__all__ = [
    "ExperimentSpec",
    "ExperimentResult",
    "SweepResult",
    "run_experiment",
    "sweep",
]
