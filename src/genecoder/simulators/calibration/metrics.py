from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from genecoder.simulators.batch_utils import mutation_counts

from .datasets import CalibrationSample


@dataclass(frozen=True)
class MetricSnapshot:
    samples: int
    evaluated_samples: int
    total_bases: int
    substitutions: int
    insertions: int
    deletions: int
    dropout_count: int
    substitution_rate: float
    insertion_rate: float
    deletion_rate: float
    dropout_rate: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "samples": self.samples,
            "evaluated_samples": self.evaluated_samples,
            "total_bases": self.total_bases,
            "substitutions": self.substitutions,
            "insertions": self.insertions,
            "deletions": self.deletions,
            "dropout_count": self.dropout_count,
            "substitution_rate": self.substitution_rate,
            "insertion_rate": self.insertion_rate,
            "deletion_rate": self.deletion_rate,
            "dropout_rate": self.dropout_rate,
        }


def compute_metrics(samples: Iterable[CalibrationSample]) -> MetricSnapshot:
    total_bases = substitutions = insertions = deletions = dropout_count = 0
    sample_list = list(samples)
    evaluated = 0
    for sample in sample_list:
        if sample.dropped:
            dropout_count += 1
            continue
        sub, ins, dels = mutation_counts(sample.original, sample.observed)
        substitutions += sub
        insertions += ins
        deletions += dels
        total_bases += len(sample.original)
        evaluated += 1

    denom = max(1, total_bases)
    total_samples = max(1, len(sample_list))
    return MetricSnapshot(
        samples=len(sample_list),
        evaluated_samples=evaluated,
        total_bases=total_bases,
        substitutions=substitutions,
        insertions=insertions,
        deletions=deletions,
        dropout_count=dropout_count,
        substitution_rate=substitutions / denom,
        insertion_rate=insertions / denom,
        deletion_rate=deletions / denom,
        dropout_rate=dropout_count / total_samples,
    )


def compute_deltas(baseline: MetricSnapshot, calibrated: MetricSnapshot) -> dict[str, float]:
    return {
        "substitution_delta": calibrated.substitution_rate - baseline.substitution_rate,
        "insertion_delta": calibrated.insertion_rate - baseline.insertion_rate,
        "deletion_delta": calibrated.deletion_rate - baseline.deletion_rate,
        "dropout_delta": calibrated.dropout_rate - baseline.dropout_rate,
    }
