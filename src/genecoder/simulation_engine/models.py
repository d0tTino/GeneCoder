from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class MutationTotals:
    substitutions: int = 0
    insertions: int = 0
    deletions: int = 0


@dataclass(frozen=True)
class EncodedOligo:
    oligo_id: str
    header: str
    index: int
    sequence: str
    seed: int | None = None


@dataclass(frozen=True)
class EncodedPool:
    batch_id: str
    oligos: tuple[EncodedOligo, ...]
    seed: int | None = None
    legacy: bool = False


@dataclass(frozen=True)
class SynthesisRecord:
    oligo: EncodedOligo
    synthesis_failed: bool = False


@dataclass(frozen=True)
class SynthesisOutput:
    batch_id: str
    records: tuple[SynthesisRecord, ...]


@dataclass(frozen=True)
class StoredRecord:
    oligo: EncodedOligo
    synthesis_failed: bool
    dropped_out: bool
    planned_coverage: int


@dataclass(frozen=True)
class StoredPool:
    batch_id: str
    records: tuple[StoredRecord, ...]


@dataclass(frozen=True)
class ReadRecord:
    oligo: EncodedOligo
    consensus: str
    coverage: int
    dropped_out: bool
    synthesis_failed: bool
    mutation_totals: MutationTotals = field(default_factory=MutationTotals)


@dataclass(frozen=True)
class ReadSet:
    batch_id: str
    reads: tuple[ReadRecord, ...]


@dataclass(frozen=True)
class DecodeInput:
    batch_id: str
    reads: tuple[ReadRecord, ...]


@dataclass(frozen=True)
class StageMetrics:
    stage: str
    oligo_count: int
    synthesis_failures: int = 0
    dropout_total: int = 0
    total_coverage: int = 0
    mutation_totals: MutationTotals = field(default_factory=MutationTotals)
    details: Mapping[str, float | int | str] = field(default_factory=dict)
