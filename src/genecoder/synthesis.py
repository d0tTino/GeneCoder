from __future__ import annotations

"""Helpers for DNA synthesis constraints."""

from dataclasses import dataclass

from .constraints import (
    ConstraintEngine,
    ConstraintPolicy,
    ConstraintRuleSet,
    GcRangeRule,
    HomopolymerMaxRule,
    LengthRule,
    MotifAllowRule,
    MotifDenyRule,
)


@dataclass
class SynthesisConstraints:
    """Synthesis constraints represented as a reusable rule set."""

    min_length: int = 25
    max_length: int = 300
    max_homopolymer: int = 3
    gc_min: float = 0.45
    gc_max: float = 0.55
    deny_motifs: tuple[str, ...] = ()
    allow_motifs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.min_length <= 0:
            raise ValueError("min_length must be greater than 0")
        if self.max_length <= 0:
            raise ValueError("max_length must be greater than 0")
        if self.min_length > self.max_length:
            raise ValueError("min_length cannot be greater than max_length")
        if not 0.0 <= self.gc_min <= 1.0:
            raise ValueError("gc_min must be between 0.0 and 1.0")
        if not 0.0 <= self.gc_max <= 1.0:
            raise ValueError("gc_max must be between 0.0 and 1.0")
        if self.gc_min > self.gc_max:
            raise ValueError("gc_min cannot be greater than gc_max")


    def to_policy(self) -> ConstraintPolicy:
        return ConstraintPolicy(
            min_length=self.min_length,
            max_length=self.max_length,
            gc_min=self.gc_min,
            gc_max=self.gc_max,
            max_homopolymer=self.max_homopolymer,
            restriction_site_bans=tuple(self.deny_motifs),
            required_motifs=tuple(self.allow_motifs),
        )

    @classmethod
    def from_policy(cls, policy: ConstraintPolicy) -> "SynthesisConstraints":
        return cls(
            min_length=policy.min_length,
            max_length=policy.max_length,
            max_homopolymer=policy.max_homopolymer,
            gc_min=policy.gc_min,
            gc_max=policy.gc_max,
            deny_motifs=tuple(policy.restriction_site_bans),
            allow_motifs=tuple(policy.required_motifs),
        )

    def to_rule_set(self) -> ConstraintRuleSet:
        rules = [
            LengthRule(min_length=self.min_length, max_length=self.max_length),
            HomopolymerMaxRule(max_homopolymer=self.max_homopolymer),
            GcRangeRule(gc_min=self.gc_min, gc_max=self.gc_max),
        ]
        if self.deny_motifs:
            rules.append(MotifDenyRule(motifs=tuple(self.deny_motifs)))
        if self.allow_motifs:
            rules.append(MotifAllowRule(motifs=tuple(self.allow_motifs)))
        return ConstraintRuleSet(rules=rules)

    def to_engine(self) -> ConstraintEngine:
        return ConstraintEngine(self.to_rule_set())


def validate_sequence(seq: str, constraints: SynthesisConstraints | None = None) -> bool:
    if constraints is None:
        constraints = SynthesisConstraints()
    report = constraints.to_engine().validate(seq)
    return report.count == 0
