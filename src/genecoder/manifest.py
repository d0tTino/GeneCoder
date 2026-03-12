from __future__ import annotations

"""Utilities for creating encode manifests."""

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping
from pathlib import Path
import os

from .results.schema import translate_manifest

REQUIRED_ENCODING_KEYS: set[str] = {"method"}


def _optimization_summary(metrics: Mapping[str, Any]) -> dict[str, Any] | None:
    outcomes = metrics.get("constraint_outcomes")
    if not isinstance(outcomes, Mapping):
        return None
    stages = outcomes.get("stages")
    if not isinstance(stages, list) or not stages:
        return None
    stage = stages[0] if isinstance(stages[0], Mapping) else {}
    tradeoff = stage.get("objective_tradeoff") if isinstance(stage.get("objective_tradeoff"), Mapping) else {}
    return {
        "mode": tradeoff.get("optimization_mode", "fixed_checks"),
        "candidate_count": tradeoff.get("candidate_count", 1),
        "objective_score": stage.get("objective_score"),
        "weighted_objectives": dict(tradeoff),
    }


def generate_manifest(
    file_name: str | os.PathLike[str],
    encoding_params: Mapping[str, Any] | object,
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a manifest dictionary for an encoded file.

    ``encoding_params`` may be either a dataclass instance or a mapping. Passing
    anything else will raise :class:`ValueError`.
    """
    if is_dataclass(encoding_params) and not isinstance(encoding_params, type):
        params = asdict(encoding_params)
    elif isinstance(encoding_params, Mapping):
        params = dict(encoding_params)
    else:
        raise ValueError("encoding_params must be a dataclass or mapping")

    missing_keys = REQUIRED_ENCODING_KEYS - params.keys()
    if missing_keys:
        missing = ", ".join(sorted(missing_keys))
        raise ValueError(f"Missing required encoding parameter(s): {missing}")

    file_basename = os.path.basename(Path(file_name).as_posix())

    metrics_payload = dict(metrics)
    opt_summary = _optimization_summary(metrics_payload)
    if opt_summary is not None:
        metrics_payload.setdefault("optimization_summary", opt_summary)
    return translate_manifest({"file": file_basename, "encoding_parameters": params, "metrics": metrics_payload})
