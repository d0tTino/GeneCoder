"""Helpers for collecting mutation statistics during simulations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .batch_utils import mutation_counts

__all__ = ["MutationObservation"]


@dataclass
class MutationObservation:
    """Aggregate substitution, insertion and deletion counts."""

    substitutions: int = 0
    insertions: int = 0
    deletions: int = 0
    opportunities: int = 0

    def record(self, reference: str, observed: str) -> Tuple[int, int, int]:
        """Record errors between ``reference`` and ``observed`` reads."""

        subs, ins, dels = mutation_counts(reference, observed)
        self.substitutions += subs
        self.insertions += ins
        self.deletions += dels
        self.opportunities += len(reference)
        return subs, ins, dels

    def extend(
        self, substitutions: int, insertions: int, deletions: int, opportunities: int
    ) -> None:
        """Extend the observation with pre-counted values."""

        self.substitutions += substitutions
        self.insertions += insertions
        self.deletions += deletions
        self.opportunities += max(0, opportunities)

    def rates(self) -> dict[str, float]:
        """Return per-base error rates derived from the current counts."""

        denom = self.opportunities or 1
        return {
            "substitution_rate": self.substitutions / denom,
            "insertion_rate": self.insertions / denom,
            "deletion_rate": self.deletions / denom,
        }

    def as_dict(self) -> dict[str, int]:
        """Return a dictionary representation of the current totals."""

        return {
            "substitutions": self.substitutions,
            "insertions": self.insertions,
            "deletions": self.deletions,
            "opportunities": self.opportunities,
        }
