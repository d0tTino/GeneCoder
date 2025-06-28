"""Common base classes for sequencing simulators."""
from __future__ import annotations

from typing import Sequence


__all__ = ["BaseSimulator"]


class BaseSimulator:
    """Base class for read simulators with simple error settings."""

    substitution_rate: float
    insertion_rate: float
    deletion_rate: float
    coverage: int
    read_length: int
    quality_profile: tuple[float, ...] | None

    def __init__(
        self,
        substitution_rate: float = 0.0,
        insertion_rate: float = 0.0,
        deletion_rate: float = 0.0,
        coverage: int = 1,
        read_length: int = 150,
        quality_profile: Sequence[float] | None = None,
    ) -> None:
        self.substitution_rate = substitution_rate
        self.insertion_rate = insertion_rate
        self.deletion_rate = deletion_rate
        self.coverage = coverage
        self.read_length = read_length
        self.quality_profile = (
            tuple(quality_profile) if quality_profile is not None else None
        )

    def get_coverage(self, sequence: str) -> int:
        """Hook returning desired coverage for ``sequence``."""
        return self.coverage

    def get_read_length(self, sequence: str) -> int:
        """Hook returning read length for ``sequence``."""
        return self.read_length

    def get_quality_profile(self, sequence: str, length: int) -> Sequence[float] | None:
        """Hook returning per-base quality values for ``sequence``."""
        if self.quality_profile is None:
            return None
        if len(self.quality_profile) >= length:
            return self.quality_profile[:length]
        if not self.quality_profile:
            return None
        tail = self.quality_profile[-1]
        return self.quality_profile + (tail,) * (length - len(self.quality_profile))

    def simulate(self, sequence: str) -> str:  # pragma: no cover - abstract
        """Return a possibly corrupted version of ``sequence``."""
        raise NotImplementedError
