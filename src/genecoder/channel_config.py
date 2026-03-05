from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

__all__ = ["ChannelConfig"]


@dataclass
class ChannelConfig:
    """Configuration options for :class:`~genecoder.simulators.pipeline.ChannelPipeline`."""

    parallel: bool = False
    workers: int | None = None
    use_process_pool: bool = False
    use_mpi: bool = False
    illumina_profile: str | None = None
    nanopore_profile: str | None = None
    illumina_parameters: Mapping[str, Any] | None = None
    nanopore_parameters: Mapping[str, Any] | None = None
    profile_parameters: Mapping[str, Any] | None = None
    dropout_rate: float | None = None
    coverage_distribution: dict[int, float] | None = None
    synthesis_loss: float | None = None
