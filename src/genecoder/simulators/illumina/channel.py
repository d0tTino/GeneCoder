"""Illumina channel implementation."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Sequence, cast
import random

from ..base import BaseSimulator
from ...formats import SequenceBatch
from ...random_utils import make_rng
from ..error_metrics import MutationObservation
from .batch import simulate_batch as _simulate_batch
from .mutations import mutate_read
from .profiles import (
    ILLUMINA_PROFILES,
    IlluminaProfile,
    _parse_quality_profile,
    _resolve_profile,
    _validate_profile,
)
from .utils import consensus, poisson


__all__ = ["IlluminaChannel", "IlluminaProfile", "ILLUMINA_PROFILES"]


class IlluminaChannel(BaseSimulator):
    """Channel modeling basic Illumina read errors."""

    supports_batches = True

    def __init__(
        self,
        substitution_rate: float | None = None,
        insertion_rate: float | None = None,
        deletion_rate: float | None = None,
        coverage: float | None = None,
        read_length: int | None = None,
        quality_profile: Sequence[float] | None = None,
        context_errors: Dict[str, float] | None = None,
        profile: str | None = None,
    ) -> None:
        profile_defaults, profile_data = _resolve_profile(profile)

        substitution_rate = float(
            substitution_rate
            if substitution_rate is not None
            else (
                profile_defaults.substitution_rate
                if profile_defaults is not None
                else 0.001
            )
        )
        insertion_rate = float(
            insertion_rate
            if insertion_rate is not None
            else (
                profile_defaults.insertion_rate
                if profile_defaults is not None
                else 0.0001
            )
        )
        deletion_rate = float(
            deletion_rate
            if deletion_rate is not None
            else (
                profile_defaults.deletion_rate
                if profile_defaults is not None
                else 0.0001
            )
        )
        read_length = int(
            read_length
            if read_length is not None
            else (
                profile_defaults.read_length if profile_defaults is not None else 150
            )
        )
        coverage = float(
            coverage
            if coverage is not None
            else (profile_defaults.coverage if profile_defaults is not None else 1)
        )
        quality_profile = (
            profile_data.get("quality_profile", quality_profile)
            if profile_data
            else quality_profile
        )
        context_errors = (
            profile_data.get("context_errors", context_errors)
            if profile_data
            else context_errors
        )

        profile_obj = _validate_profile(
            {
                "substitution_rate": substitution_rate,
                "insertion_rate": insertion_rate,
                "deletion_rate": deletion_rate,
                "read_length": read_length,
                "coverage": coverage,
            }
        )
        substitution_rate = profile_obj.substitution_rate
        insertion_rate = profile_obj.insertion_rate
        deletion_rate = profile_obj.deletion_rate
        read_length = profile_obj.read_length
        coverage = profile_obj.coverage

        if isinstance(quality_profile, str):
            quality_profile = _parse_quality_profile(quality_profile)

        super().__init__(
            substitution_rate=substitution_rate,
            insertion_rate=insertion_rate,
            deletion_rate=deletion_rate,
            coverage=coverage,
            read_length=read_length,
            quality_profile=quality_profile,
        )
        self.context_errors = {
            k.upper(): float(v) for k, v in (context_errors or {}).items()
        }

    def _mutate_read(
        self, read: str, quality: Sequence[float] | None, rng: random.Random
    ) -> str:
        return cast(
            str,
            mutate_read(
                read,
                quality,
                rng,
                substitution_rate=self.substitution_rate,
                insertion_rate=self.insertion_rate,
                deletion_rate=self.deletion_rate,
                context_errors=self.context_errors,
            ),
        )

    @staticmethod
    def _consensus(reads: Sequence[str]) -> str:
        return consensus(reads)

    _simulate_batch = staticmethod(_simulate_batch)

    def simulate(self, sequence: str | SequenceBatch) -> str | SequenceBatch:
        if isinstance(sequence, SequenceBatch):
            return self._simulate_batch(sequence)
        return self._simulate_string(sequence)

    def _simulate_batch(self, batch: SequenceBatch) -> SequenceBatch:
        return _simulate_batch(self, batch)

    def _simulate_string(self, sequence: str) -> str:
        rng = make_rng()
        read_length = self.get_read_length(sequence)
        read = sequence[:read_length]
        quality = self.get_quality_profile(sequence, read_length)
        coverage = max(1, poisson(self.coverage, rng))
        reads = [self._mutate_read(read, quality, rng) for _ in range(coverage)]
        if coverage == 1:
            return reads[0]
        return self._consensus(reads)

    def observe_error_rates(
        self,
        sequence: str,
        *,
        reads: int | None = None,
        seed: int | None = None,
    ) -> MutationObservation:
        """Return aggregate mutation counts for ``sequence``.

        This helper enables deterministic regression tests that validate the
        substitution/insertion/deletion parameters baked into Illumina
        profiles.
        """

        rng = random.Random(seed if seed is not None else 0)
        read_length = self.get_read_length(sequence)
        template = sequence[:read_length]
        quality = self.get_quality_profile(sequence, read_length)
        total_reads = reads if reads is not None else max(1, int(self.coverage))
        observation = MutationObservation()
        for _ in range(total_reads):
            mutate_read(
                template,
                quality,
                rng,
                substitution_rate=self.substitution_rate,
                insertion_rate=self.insertion_rate,
                deletion_rate=self.deletion_rate,
                context_errors=self.context_errors,
                observation=observation,
            )
        return observation

    def with_profile(self, profile: str) -> "IlluminaChannel":
        """Return a new channel configured to use ``profile``.

        Unknown profiles leave the channel unchanged.
        """

        path = Path(profile)
        if not path.is_file() and profile.lower() not in ILLUMINA_PROFILES:
            return self
        return type(self)(
            substitution_rate=self.substitution_rate,
            insertion_rate=self.insertion_rate,
            deletion_rate=self.deletion_rate,
            coverage=self.coverage,
            read_length=self.read_length,
            quality_profile=self.quality_profile,
            context_errors=dict(self.context_errors),
            profile=profile,
        )
