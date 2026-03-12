from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from .datasets import CalibrationDataset
from .metrics import MetricSnapshot

Profile = dict[str, float]
ProfileFitHook = Callable[[Profile, CalibrationDataset, MetricSnapshot], Profile]


@dataclass(frozen=True)
class FitResult:
    fitted_profile: Profile
    hook_name: str


def fit_profile(
    *,
    initial_profile: Mapping[str, float] | None,
    dataset: CalibrationDataset,
    calibrated_metrics: MetricSnapshot,
    hook: ProfileFitHook | None = None,
) -> FitResult:
    profile: Profile = {
        "substitution_rate": float(initial_profile.get("substitution_rate", 0.0)) if initial_profile else 0.0,
        "insertion_rate": float(initial_profile.get("insertion_rate", 0.0)) if initial_profile else 0.0,
        "deletion_rate": float(initial_profile.get("deletion_rate", 0.0)) if initial_profile else 0.0,
        "dropout_rate": float(initial_profile.get("dropout_rate", 0.0)) if initial_profile else 0.0,
    }
    profile.update(
        {
            "substitution_rate": calibrated_metrics.substitution_rate,
            "insertion_rate": calibrated_metrics.insertion_rate,
            "deletion_rate": calibrated_metrics.deletion_rate,
            "dropout_rate": calibrated_metrics.dropout_rate,
        }
    )

    if hook is None:
        return FitResult(fitted_profile=profile, hook_name="default")
    return FitResult(
        fitted_profile=hook(profile, dataset, calibrated_metrics),
        hook_name=getattr(hook, "__name__", "custom_hook"),
    )
