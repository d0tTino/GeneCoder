"""Utilities to repair DNA sequences to satisfy synthesis constraints."""

from __future__ import annotations

import random
from dataclasses import dataclass

from .constraints import (
    ConstraintEngine,
    ConstraintRuleSet,
    DNAChiselSolverBackend,
    DeterministicRepairStrategy,
    ExternalSolverRepairStrategy,
    GcRangeRule,
    HomopolymerMaxRule,
    StochasticRepairStrategy,
)
from .gc_constrained_encoder import calculate_gc_content
from .random_utils import make_rng
from .utils import get_max_homopolymer_length

__all__ = [
    "adjust_gc_balance",
    "limit_homopolymers",
    "fix_sequence",
    "fix_sequence_with_report",
    "fix",
    "encode",
]


@dataclass
class StrategyPlugin:
    name: str

    def build(self, *, rng: random.Random | None = None):
        if self.name == "deterministic":
            return DeterministicRepairStrategy()
        if self.name == "stochastic":
            return StochasticRepairStrategy(rng=rng)
        if self.name == "external_solver":
            return ExternalSolverRepairStrategy(solver_backend=DNAChiselSolverBackend())
        raise ValueError(f"Unknown strategy '{self.name}'")


def _rule_set(target_gc_min: float, target_gc_max: float, max_homopolymer: int) -> ConstraintRuleSet:
    return ConstraintRuleSet(
        rules=[
            GcRangeRule(gc_min=target_gc_min, gc_max=target_gc_max),
            HomopolymerMaxRule(max_homopolymer=max_homopolymer),
        ]
    )


def adjust_gc_balance(
    sequence: str,
    target_gc_min: float,
    target_gc_max: float,
    *,
    rng: random.Random | None = None,
) -> str:
    report = fix_sequence_with_report(
        sequence,
        target_gc_min=target_gc_min,
        target_gc_max=target_gc_max,
        max_homopolymer=max(1, len(sequence) + 1),
        strategy="stochastic",
        rng=rng,
    )
    return report[0]


def limit_homopolymers(
    sequence: str,
    max_len: int,
    *,
    rng: random.Random | None = None,
) -> str:
    report = fix_sequence_with_report(
        sequence,
        target_gc_min=0.0,
        target_gc_max=1.0,
        max_homopolymer=max_len,
        strategy="stochastic",
        rng=rng,
    )
    return report[0]


def fix_sequence_with_report(
    sequence: str,
    *,
    target_gc_min: float,
    target_gc_max: float,
    max_homopolymer: int,
    strategy: str = "stochastic",
    rng: random.Random | None = None,
) -> tuple[str, dict[str, object]]:
    if target_gc_min > target_gc_max:
        raise ValueError("target_gc_min cannot exceed target_gc_max")
    if max_homopolymer < 1:
        raise ValueError("max_homopolymer must be at least 1")

    plugin = StrategyPlugin(strategy)
    engine = ConstraintEngine(_rule_set(target_gc_min, target_gc_max, max_homopolymer))
    repair_strategy = plugin.build(rng=rng or make_rng())
    after_report, repair_result = engine.repair(sequence.upper(), repair_strategy)
    payload = {
        "strategy": repair_result.strategy,
        "reason": repair_result.reason,
        "changes": [
            {
                "start": change.start,
                "end": change.end,
                "before": change.before,
                "after": change.after,
                "reason": change.reason,
            }
            for change in repair_result.changes
        ],
        "metadata": repair_result.metadata,
        "remaining_violations": [v.rule_id for v in after_report.violations],
    }
    return repair_result.sequence_after, payload


def fix_sequence(
    sequence: str,
    *,
    target_gc_min: float,
    target_gc_max: float,
    max_homopolymer: int,
    rng: random.Random | None = None,
) -> str:
    fixed, _report = fix_sequence_with_report(
        sequence,
        target_gc_min=target_gc_min,
        target_gc_max=target_gc_max,
        max_homopolymer=max_homopolymer,
        strategy="stochastic",
        rng=rng,
    )
    return fixed


def fix(
    sequence: str,
    *,
    gc_min: float,
    gc_max: float,
    max_homopolymer: int,
    rng: random.Random | None = None,
) -> str:
    return fix_sequence(
        sequence,
        target_gc_min=gc_min,
        target_gc_max=gc_max,
        max_homopolymer=max_homopolymer,
        rng=rng,
    )


def encode(
    sequence: str,
    *,
    gc_min: float,
    gc_max: float,
    max_homopolymer: int,
    rng: random.Random | None = None,
    strategy: str = "stochastic",
) -> tuple[str, dict[str, object]]:
    fixed, repair_report = fix_sequence_with_report(
        sequence,
        target_gc_min=gc_min,
        target_gc_max=gc_max,
        max_homopolymer=max_homopolymer,
        strategy=strategy,
        rng=rng,
    )
    metrics: dict[str, object] = {
        "gc_content": calculate_gc_content(fixed),
        "max_homopolymer": get_max_homopolymer_length(fixed),
        "repair_report": repair_report,
    }
    return fixed, metrics
