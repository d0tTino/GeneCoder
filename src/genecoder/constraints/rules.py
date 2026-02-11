from __future__ import annotations

from dataclasses import dataclass, field

from genecoder.gc_constrained_encoder import calculate_gc_content
from genecoder.utils import get_max_homopolymer_length

from .report import ConstraintViolation, ViolationLocation


class ConstraintRule:
    rule_id: str

    def validate(self, sequence: str) -> list[ConstraintViolation]:
        raise NotImplementedError


@dataclass(frozen=True)
class GcRangeRule(ConstraintRule):
    gc_min: float
    gc_max: float
    rule_id: str = "gc_range"

    def validate(self, sequence: str) -> list[ConstraintViolation]:
        if not sequence:
            return []
        gc = calculate_gc_content(sequence)
        if self.gc_min <= gc <= self.gc_max:
            return []
        status = "below" if gc < self.gc_min else "above"
        return [
            ConstraintViolation(
                rule_id=self.rule_id,
                message=f"GC content {gc:.3f} is {status} allowed range [{self.gc_min:.3f}, {self.gc_max:.3f}]",
                details={"gc_content": gc, "gc_min": self.gc_min, "gc_max": self.gc_max},
            )
        ]


@dataclass(frozen=True)
class HomopolymerMaxRule(ConstraintRule):
    max_homopolymer: int
    rule_id: str = "homopolymer_max"

    def validate(self, sequence: str) -> list[ConstraintViolation]:
        run = get_max_homopolymer_length(sequence)
        if run <= self.max_homopolymer:
            return []
        return [
            ConstraintViolation(
                rule_id=self.rule_id,
                message=f"Maximum homopolymer run {run} exceeds {self.max_homopolymer}",
                details={"max_observed": run, "max_allowed": self.max_homopolymer},
            )
        ]


@dataclass(frozen=True)
class LengthRule(ConstraintRule):
    min_length: int
    max_length: int
    rule_id: str = "length"

    def validate(self, sequence: str) -> list[ConstraintViolation]:
        length = len(sequence)
        if self.min_length <= length <= self.max_length:
            return []
        status = "short" if length < self.min_length else "long"
        return [
            ConstraintViolation(
                rule_id=self.rule_id,
                message=f"Sequence length {length} is too {status}; allowed [{self.min_length}, {self.max_length}]",
                details={"length": length, "min_length": self.min_length, "max_length": self.max_length},
            )
        ]


@dataclass(frozen=True)
class MotifDenyRule(ConstraintRule):
    motifs: tuple[str, ...]
    rule_id: str = "motif_deny"

    def validate(self, sequence: str) -> list[ConstraintViolation]:
        seq = sequence.upper()
        violations: list[ConstraintViolation] = []
        for motif in self.motifs:
            needle = motif.upper()
            start = seq.find(needle)
            while start != -1:
                violations.append(
                    ConstraintViolation(
                        rule_id=self.rule_id,
                        message=f"Denied motif '{needle}' found",
                        location=ViolationLocation(start=start, end=start + len(needle)),
                        details={"motif": needle},
                    )
                )
                start = seq.find(needle, start + 1)
        return violations


@dataclass(frozen=True)
class MotifAllowRule(ConstraintRule):
    motifs: tuple[str, ...]
    rule_id: str = "motif_allow"

    def validate(self, sequence: str) -> list[ConstraintViolation]:
        if not self.motifs:
            return []
        seq = sequence.upper()
        if any(motif.upper() in seq for motif in self.motifs):
            return []
        return [
            ConstraintViolation(
                rule_id=self.rule_id,
                message="Sequence does not contain any required motifs",
                details={"required_motifs": list(self.motifs)},
            )
        ]


@dataclass
class ConstraintRuleSet:
    rules: list[ConstraintRule] = field(default_factory=list)

    def validate(self, sequence: str) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        for rule in self.rules:
            violations.extend(rule.validate(sequence))
        return violations

    def limits(self) -> dict[str, float | int | list[str]]:
        details: dict[str, float | int | list[str]] = {}
        for rule in self.rules:
            if isinstance(rule, GcRangeRule):
                details["gc_min"] = rule.gc_min
                details["gc_max"] = rule.gc_max
            elif isinstance(rule, HomopolymerMaxRule):
                details["max_homopolymer"] = rule.max_homopolymer
            elif isinstance(rule, LengthRule):
                details["min_length"] = rule.min_length
                details["max_length"] = rule.max_length
            elif isinstance(rule, MotifDenyRule):
                details["deny_motifs"] = list(rule.motifs)
            elif isinstance(rule, MotifAllowRule):
                details["allow_motifs"] = list(rule.motifs)
        return details
