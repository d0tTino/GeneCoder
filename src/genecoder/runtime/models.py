from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from genecoder.constraints import ConstraintPolicy
from genecoder.formats import SequenceBatch
from genecoder.runtime import RunContext


@dataclass(slots=True)
class EncodeStageInput:
    codec: str
    fec: str | None
    data: bytes
    constraint_policy: ConstraintPolicy | None = None
    run_context: RunContext | None = None


@dataclass(slots=True)
class EncodeStageOutput:
    encoded_batch: SequenceBatch
    fec_info: Mapping[str, Any] | None


@dataclass(slots=True)
class SimulateStageInput:
    channel: str | None
    dna: SequenceBatch | str
    channel_parameters: Mapping[str, Any] | None = None
    run_context: RunContext | None = None


@dataclass(slots=True)
class SimulateStageOutput:
    dna: SequenceBatch | str
    substitutions: int | None
    insertions: int | None
    deletions: int | None
    coverage: int | None


@dataclass(slots=True)
class DecodeStageInput:
    codec: str
    fec: str | None
    dna: SequenceBatch | str
    fec_info: Mapping[str, Any] | None
    filter_mutated: bool = True
    survivor_batch: SequenceBatch | None = None
    constraint_policy: ConstraintPolicy | None = None
    run_context: RunContext | None = None


@dataclass(slots=True)
class DecodeStageOutput:
    decoded: bytes


@dataclass(slots=True)
class ConstraintStageInput:
    batch: SequenceBatch
    policy: ConstraintPolicy
    stage: str


@dataclass(slots=True)
class ConstraintStageOutput:
    payload: dict[str, Any]
