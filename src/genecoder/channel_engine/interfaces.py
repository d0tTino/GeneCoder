from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..formats import SequenceBatch


@dataclass(frozen=True)
class StageResult:
    """Result payload emitted by a channel stage."""

    batch: SequenceBatch
    profile_version: str | None = None


class Stage(Protocol):
    """Common protocol implemented by all channel stages."""

    stage_name: str

    def run(self, batch: SequenceBatch, *, profile: str | None = None) -> StageResult:
        """Process ``batch`` and return a new :class:`StageResult`."""


class SynthesisStage(Stage, Protocol):
    """Stage protocol for synthesis loss and early corruption."""


class StorageStage(Stage, Protocol):
    """Stage protocol for storage/decay modeling."""


class SequencingStage(Stage, Protocol):
    """Stage protocol for sequencing/readout modeling."""
