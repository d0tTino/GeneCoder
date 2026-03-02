from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Mapping, Protocol

from ..formats import SequenceBatch
from ..runtime import RunContext


@dataclass(frozen=True)
class StageMutationTotals:
    """Canonical mutation accounting for a stage execution."""

    substitutions: int = 0
    insertions: int = 0
    deletions: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "substitutions": int(self.substitutions),
            "insertions": int(self.insertions),
            "deletions": int(self.deletions),
        }


@dataclass(frozen=True)
class StageContext:
    """Execution context passed to every simulator stage."""

    run_context: RunContext
    seed: int | None
    rng: random.Random
    metadata: Mapping[str, str]


@dataclass(frozen=True)
class StageProvenance:
    """Canonical provenance emitted by each stage execution."""

    stage_name: str
    stage_kind: str
    profile: str | None
    profile_version: str | None
    seed: int | None
    mutation_totals: StageMutationTotals = field(default_factory=StageMutationTotals)
    metadata: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "stage_name": self.stage_name,
            "stage_kind": self.stage_kind,
            "profile": self.profile,
            "profile_version": self.profile_version,
            "seed": self.seed,
            "mutation_totals": self.mutation_totals.to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class StageResult:
    """Canonical stage output contract."""

    output_batch: SequenceBatch
    profile_version: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)


class SimulatorStage(Protocol):
    """Common protocol implemented by all channel stages."""

    stage_name: str

    def run(
        self,
        input_batch: SequenceBatch,
        *,
        profile: str | None = None,
        context: StageContext,
    ) -> StageResult:
        """Process ``input_batch`` and return canonical stage outputs."""


class SynthesisStage(SimulatorStage, Protocol):
    """Stage protocol for synthesis loss and early corruption."""


class StorageStage(SimulatorStage, Protocol):
    """Stage protocol for storage/decay modeling."""


class SequencingStage(SimulatorStage, Protocol):
    """Stage protocol for sequencing/readout modeling."""
