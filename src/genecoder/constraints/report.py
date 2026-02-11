from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Literal

Severity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class ViolationLocation:
    start: int
    end: int


@dataclass(frozen=True)
class ConstraintViolation:
    rule_id: str
    message: str
    severity: Severity = "error"
    location: ViolationLocation | None = None
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RepairChange:
    start: int
    end: int
    before: str
    after: str
    reason: str


@dataclass(frozen=True)
class RepairResult:
    strategy: str
    sequence_before: str
    sequence_after: str
    changes: list[RepairChange]
    reason: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ConstraintReport:
    sequence: str
    violations: list[ConstraintViolation]

    @property
    def count(self) -> int:
        return len(self.violations)

    @property
    def pressure(self) -> float:
        if not self.sequence:
            return float(self.count)
        return self.count / len(self.sequence)


def build_diff_changes(before: str, after: str, *, reason: str) -> list[RepairChange]:
    matcher = SequenceMatcher(a=before, b=after)
    changes: list[RepairChange] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        changes.append(
            RepairChange(
                start=i1,
                end=i2,
                before=before[i1:i2],
                after=after[j1:j2],
                reason=reason,
            )
        )
    return changes
