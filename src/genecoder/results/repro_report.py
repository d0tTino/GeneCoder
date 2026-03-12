from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from genecoder.config.loader import load_mapping_file
from genecoder.results.schema import canonical_comparison_metrics, migrate_run_schema

DEFAULT_REPRO_CONFIG_PATH = (
    Path(__file__).resolve().parents[3] / "configs" / "reproducibility.yaml"
)


@dataclass(frozen=True)
class ReproCheck:
    metric: str
    baseline: float | bool | None
    candidate: float | bool | None
    within_tolerance: bool
    tolerance: Mapping[str, Any]
    delta: float | None


def load_reproducibility_config(
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(config_path) if config_path else DEFAULT_REPRO_CONFIG_PATH
    loaded = load_mapping_file(source)
    return dict(loaded)


def _normalize_profile(run_data: Mapping[str, Any]) -> str:
    profiles = run_data.get("profiles")
    if not isinstance(profiles, Mapping):
        return "unknown"
    simulation = profiles.get("simulation")
    if simulation is None:
        return "unknown"
    return str(simulation)


def _normalize_seed(run_data: Mapping[str, Any]) -> str:
    seeds = run_data.get("seeds")
    if not isinstance(seeds, Mapping):
        return "unset"
    seed = seeds.get("global")
    if seed is None:
        return "unset"
    return str(seed)


def _float_value(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _evaluate_metric(
    metric: str,
    baseline: float | bool | None,
    candidate: float | bool | None,
    tolerance: Mapping[str, Any],
) -> ReproCheck:
    if isinstance(baseline, bool) or isinstance(candidate, bool):
        within = baseline == candidate
        return ReproCheck(
            metric=metric,
            baseline=baseline,
            candidate=candidate,
            within_tolerance=within,
            tolerance=tolerance,
            delta=None,
        )

    baseline_num = _float_value(baseline)
    candidate_num = _float_value(candidate)
    if baseline_num is None or candidate_num is None:
        return ReproCheck(
            metric=metric,
            baseline=baseline,
            candidate=candidate,
            within_tolerance=False,
            tolerance=tolerance,
            delta=None,
        )

    mode = str(tolerance.get("mode", "absolute"))
    max_delta = float(tolerance.get("max_delta", 0.0))
    delta = abs(candidate_num - baseline_num)
    if mode == "relative":
        denominator = abs(baseline_num) if baseline_num != 0 else 1.0
        normalized_delta = delta / denominator
        within = normalized_delta <= max_delta
    else:
        within = delta <= max_delta
    return ReproCheck(
        metric=metric,
        baseline=baseline_num,
        candidate=candidate_num,
        within_tolerance=within,
        tolerance=tolerance,
        delta=delta,
    )


def _deterministic_violations(
    metrics: Mapping[str, float | bool | None],
    expectations: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for metric, rule in expectations.items():
        if str(rule.get("type", "equals")) != "equals":
            continue
        expected = rule.get("value")
        actual = metrics.get(metric)
        if actual != expected:
            violations.append(
                {"metric": metric, "expected": expected, "actual": actual}
            )
    return violations


def generate_reproducibility_report(
    run_artifacts: Sequence[str | Path],
    *,
    config_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    config = load_reproducibility_config(config_path)
    comparison = (
        config.get("comparison")
        if isinstance(config.get("comparison"), Mapping)
        else {}
    )
    tolerances = (
        comparison.get("tolerances")
        if isinstance(comparison.get("tolerances"), Mapping)
        else {}
    )
    deterministic = (
        comparison.get("deterministic_expectations")
        if isinstance(comparison.get("deterministic_expectations"), Mapping)
        else {}
    )

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    run_index: list[dict[str, Any]] = []
    for artifact_path in run_artifacts:
        path = Path(artifact_path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        run_data = migrate_run_schema(raw)
        profile = _normalize_profile(run_data)
        seed = _normalize_seed(run_data)
        metrics = canonical_comparison_metrics(run_data)
        grouped.setdefault((profile, seed), []).append(
            {"path": str(path), "metrics": metrics, "run_id": run_data.get("run_id")}
        )
        run_index.append(
            {
                "path": str(path),
                "profile": profile,
                "seed": seed,
                "run_id": run_data.get("run_id"),
            }
        )

    comparisons: list[dict[str, Any]] = []
    tolerance_violations = 0
    deterministic_violations = 0
    for (profile, seed), runs in sorted(grouped.items()):
        if len(runs) < 2:
            continue
        baseline = runs[0]
        for candidate in runs[1:]:
            metric_checks: list[dict[str, Any]] = []
            for metric, rule in sorted(tolerances.items()):
                if not isinstance(rule, Mapping):
                    continue
                check = _evaluate_metric(
                    metric,
                    baseline["metrics"].get(metric),
                    candidate["metrics"].get(metric),
                    rule,
                )
                metric_checks.append(
                    {
                        "metric": check.metric,
                        "baseline": check.baseline,
                        "candidate": check.candidate,
                        "delta": check.delta,
                        "within_tolerance": check.within_tolerance,
                        "tolerance": dict(check.tolerance),
                    }
                )
                if not check.within_tolerance:
                    tolerance_violations += 1

            baseline_det = _deterministic_violations(
                baseline["metrics"],
                {k: v for k, v in deterministic.items() if isinstance(v, Mapping)},
            )
            candidate_det = _deterministic_violations(
                candidate["metrics"],
                {k: v for k, v in deterministic.items() if isinstance(v, Mapping)},
            )
            deterministic_violations += len(baseline_det) + len(candidate_det)
            comparisons.append(
                {
                    "profile": profile,
                    "seed": seed,
                    "baseline": baseline["path"],
                    "candidate": candidate["path"],
                    "metric_checks": metric_checks,
                    "deterministic_expectation_violations": {
                        "baseline": baseline_det,
                        "candidate": candidate_det,
                    },
                }
            )

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config_path": str(
            Path(config_path) if config_path else DEFAULT_REPRO_CONFIG_PATH
        ),
        "runs": run_index,
        "summary": {
            "group_count": len(grouped),
            "comparison_count": len(comparisons),
            "tolerance_violations": tolerance_violations,
            "deterministic_violations": deterministic_violations,
            "pass": tolerance_violations == 0 and deterministic_violations == 0,
        },
        "comparisons": comparisons,
    }
    if output_path:
        Path(output_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
