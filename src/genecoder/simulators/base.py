"""Common base classes for sequencing simulators."""
from __future__ import annotations

from typing import Sequence
from dataclasses import dataclass
from abc import abstractmethod

from ..api import Simulator


__all__ = ["BaseSimulator"]


@dataclass
class BaseSimulator(Simulator):
    """Base class for read simulators with simple error settings."""
    substitution_rate: float = 0.0
    insertion_rate: float = 0.0
    deletion_rate: float = 0.0
    coverage: int = 1
    read_length: int = 150
    quality_profile: Sequence[float] | None = None

    def __post_init__(self) -> None:
        if self.quality_profile is not None:
            self.quality_profile = tuple(self.quality_profile)

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
        profile = tuple(self.quality_profile)
        if len(profile) >= length:
            return profile[:length]
        if not profile:
            return None
        tail = profile[-1]
        return profile + (tail,) * (length - len(profile))

    @abstractmethod
    def simulate(self, sequence: str) -> str:  # pragma: no cover - abstract
        """Return a possibly corrupted version of ``sequence``."""
        raise NotImplementedError
