from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Protocol

from ..formats import SequenceBatch
from ..runtime import RunContext


@dataclass(frozen=True)
class StageContext:
    """Execution context passed to every simulator stage."""

    run_context: RunContext
    seed: int | None
    rng: random.Random
    metadata: dict[str, str]


@dataclass(frozen=True)
class StageResult:
    """Result payload emitted by a channel stage."""

    batch: SequenceBatch
    profile_version: str | None = None
    metadata: dict[str, str] | None = None


class SimulatorStage(Protocol):
    """Common protocol implemented by all channel stages."""

    stage_name: str

    def run(
        self,
        batch: SequenceBatch,
        *,
        profile: str | None = None,
        context: StageContext,
    ) -> StageResult:
        """Process ``batch`` and return a new :class:`StageResult`."""


class SynthesisStage(SimulatorStage, Protocol):
    """Stage protocol for synthesis loss and early corruption."""


class StorageStage(SimulatorStage, Protocol):
    """Stage protocol for storage/decay modeling."""


class SequencingStage(SimulatorStage, Protocol):
    """Stage protocol for sequencing/readout modeling."""
