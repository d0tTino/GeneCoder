from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .datasets import dataset_manifest, load_calibration_dataset
from .fitting import fit_profile
from .metrics import compute_deltas, compute_metrics


THRESHOLD_CONFIG_PATH = Path("configs/benchmark_thresholds.json")


@dataclass(frozen=True)
class ThresholdEvaluation:
    passed: bool
    limits: dict[str, float]
    violations: dict[str, float]

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "limits": self.limits,
            "violations": self.violations,
        }


def _load_calibration_thresholds(path: Path = THRESHOLD_CONFIG_PATH) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("calibration", {}).get("delta_thresholds", {})
    return {
        "substitution_delta": float(raw.get("substitution_delta", 1.0)),
        "insertion_delta": float(raw.get("insertion_delta", 1.0)),
        "deletion_delta": float(raw.get("deletion_delta", 1.0)),
        "dropout_delta": float(raw.get("dropout_delta", 1.0)),
    }


def evaluate_thresholds(
    deltas: Mapping[str, float],
    *,
    threshold_path: Path = THRESHOLD_CONFIG_PATH,
) -> ThresholdEvaluation:
    limits = _load_calibration_thresholds(threshold_path)
    violations: dict[str, float] = {}
    for metric, value in deltas.items():
        limit = limits.get(metric, 1.0)
        if abs(value) > limit:
            violations[metric] = abs(value)
    return ThresholdEvaluation(
        passed=not violations,
        limits=limits,
        violations=violations,
    )


def run_calibration(
    *,
    dataset_path: str,
    profile: str,
    output_root: str = "artifacts/calibration",
    run_date: str | None = None,
    threshold_path: Path = THRESHOLD_CONFIG_PATH,
) -> tuple[Path, dict[str, Any]]:
    dataset = load_calibration_dataset(dataset_path)
    baseline = compute_metrics(dataset.baseline)
    calibrated = compute_metrics(dataset.calibrated)
    deltas = compute_deltas(baseline, calibrated)
    threshold_eval = evaluate_thresholds(deltas, threshold_path=threshold_path)
    fit_result = fit_profile(
        initial_profile=None,
        dataset=dataset,
        calibrated_metrics=calibrated,
    )

    stamp = run_date or datetime.utcnow().strftime("%Y-%m-%d")
    out_dir = Path(output_root) / profile / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "profile": profile,
        "dataset_manifest": dataset_manifest(dataset),
        "baseline_metrics": baseline.as_dict(),
        "calibrated_metrics": calibrated.as_dict(),
        "deviation_summary": deltas,
        "threshold_evaluation": threshold_eval.as_dict(),
        "fitted_profile": fit_result.fitted_profile,
        "profile_fit_hook": fit_result.hook_name,
    }

    (out_dir / "dataset_manifest.json").write_text(
        json.dumps(report["dataset_manifest"], indent=2), encoding="utf-8"
    )
    (out_dir / "baseline_metrics.json").write_text(
        json.dumps(report["baseline_metrics"], indent=2), encoding="utf-8"
    )
    (out_dir / "calibrated_metrics.json").write_text(
        json.dumps(report["calibrated_metrics"], indent=2), encoding="utf-8"
    )
    (out_dir / "deviation_summary.json").write_text(
        json.dumps(
            {
                **report["deviation_summary"],
                "threshold_evaluation": report["threshold_evaluation"],
                "fitted_profile": report["fitted_profile"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return out_dir, report
