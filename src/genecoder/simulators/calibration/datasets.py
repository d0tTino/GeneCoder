from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CalibrationSample:
    """Single calibration record with optional dropout annotation."""

    sample_id: str
    original: str
    observed: str
    dropped: bool = False


@dataclass(frozen=True)
class CalibrationDataset:
    """Calibration dataset split into baseline and calibrated samples."""

    profile: str
    baseline: tuple[CalibrationSample, ...]
    calibrated: tuple[CalibrationSample, ...]
    source: Path


def _parse_samples(raw: list[dict[str, Any]], label: str) -> tuple[CalibrationSample, ...]:
    samples: list[CalibrationSample] = []
    for idx, item in enumerate(raw):
        sample_id = str(item.get("id") or f"{label}-{idx}")
        original = str(item.get("original", "")).strip().upper()
        observed = str(item.get("observed", "")).strip().upper()
        dropped = bool(item.get("dropped", False))
        if not original:
            raise ValueError(f"{label}[{idx}] is missing 'original'")
        if not dropped and not observed:
            raise ValueError(f"{label}[{idx}] is missing 'observed' for non-dropout sample")
        samples.append(
            CalibrationSample(
                sample_id=sample_id,
                original=original,
                observed=observed,
                dropped=dropped,
            )
        )
    return tuple(samples)


def load_calibration_dataset(path: str | Path) -> CalibrationDataset:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    profile = str(payload.get("profile", "unknown")).strip() or "unknown"
    baseline = _parse_samples(list(payload.get("baseline", [])), "baseline")
    calibrated = _parse_samples(list(payload.get("calibrated", [])), "calibrated")
    if not baseline or not calibrated:
        raise ValueError("Calibration dataset must contain non-empty baseline and calibrated arrays")
    return CalibrationDataset(
        profile=profile,
        baseline=baseline,
        calibrated=calibrated,
        source=Path(path),
    )


def dataset_manifest(dataset: CalibrationDataset) -> dict[str, Any]:
    return {
        "profile": dataset.profile,
        "source": dataset.source.as_posix(),
        "baseline_samples": len(dataset.baseline),
        "calibrated_samples": len(dataset.calibrated),
        "baseline_ids": [sample.sample_id for sample in dataset.baseline],
        "calibrated_ids": [sample.sample_id for sample in dataset.calibrated],
    }
