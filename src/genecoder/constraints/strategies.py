from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Protocol

from genecoder.random_utils import make_rng

from .policy import ObjectivePolicy
from .report import RepairResult, build_diff_changes
from .rules import ConstraintRuleSet, GcRangeRule, HomopolymerMaxRule


class RepairStrategy(Protocol):
    name: str

    def repair(self, sequence: str, rules: ConstraintRuleSet) -> RepairResult:
        ...


@dataclass
class DeterministicRepairStrategy:
    name: str = "deterministic"

    def repair(self, sequence: str, rules: ConstraintRuleSet) -> RepairResult:
        seq = sequence.upper()
        before = seq
        for rule in rules.rules:
            if isinstance(rule, HomopolymerMaxRule):
                seq = _limit_homopolymers(seq, rule.max_homopolymer)
            elif isinstance(rule, GcRangeRule):
                seq = _adjust_gc(seq, rule.gc_min, rule.gc_max, rng=random.Random(0))
        changes = build_diff_changes(before, seq, reason="deterministic_rule_pass")
        return RepairResult(
            strategy=self.name,
            sequence_before=before,
            sequence_after=seq,
            changes=changes,
            reason="Applied deterministic constraint repair",
        )


@dataclass
class StochasticRepairStrategy:
    rng: random.Random | None = None
    name: str = "stochastic"

    def repair(self, sequence: str, rules: ConstraintRuleSet) -> RepairResult:
        seq = sequence.upper()
        before = seq
        rng = self.rng or make_rng()
        for rule in rules.rules:
            if isinstance(rule, GcRangeRule):
                seq = _adjust_gc(seq, rule.gc_min, rule.gc_max, rng=rng)
            elif isinstance(rule, HomopolymerMaxRule):
                seq = _limit_homopolymers(seq, rule.max_homopolymer, rng=rng)
        changes = build_diff_changes(before, seq, reason="stochastic_rule_pass")
        return RepairResult(
            strategy=self.name,
            sequence_before=before,
            sequence_after=seq,
            changes=changes,
            reason="Applied stochastic constraint repair",
        )


@dataclass
class ExternalSolverRepairStrategy:
    solver_backend: "SolverBackend"
    objective_policy: ObjectivePolicy | None = None
    replay_seed: int | None = None
    name: str = "external_solver"

    def repair(self, sequence: str, rules: ConstraintRuleSet) -> RepairResult:
        return self.solver_backend.solve(
            sequence,
            rules,
            strategy_name=self.name,
            objective_policy=self.objective_policy,
            replay_seed=self.replay_seed,
        )


class SolverBackend(Protocol):
    def solve(
        self,
        sequence: str,
        rules: ConstraintRuleSet,
        *,
        strategy_name: str,
        objective_policy: ObjectivePolicy | None = None,
        replay_seed: int | None = None,
    ) -> RepairResult:
        ...


def _adjust_gc(sequence: str, gc_min: float, gc_max: float, *, rng: random.Random) -> str:
    if gc_min > gc_max:
        raise ValueError("gc_min cannot exceed gc_max")
    seq = list(sequence)
    length = len(seq)
    if length == 0:
        return ""
    gc_count = sum(1 for b in seq if b in {"G", "C"})
    gc = gc_count / length
    while gc < gc_min:
        idxs = [i for i, b in enumerate(seq) if b in {"A", "T"}]
        if not idxs:
            break
        i = rng.choice(idxs)
        seq[i] = rng.choice(["G", "C"])
        gc_count += 1
        gc = gc_count / length
    while gc > gc_max:
        idxs = [i for i, b in enumerate(seq) if b in {"G", "C"}]
        if not idxs:
            break
        i = rng.choice(idxs)
        seq[i] = rng.choice(["A", "T"])
        gc_count -= 1
        gc = gc_count / length
    return "".join(seq)


def _limit_homopolymers(sequence: str, max_len: int, *, rng: random.Random | None = None) -> str:
    if max_len < 1:
        raise ValueError("max_len must be at least 1")
    effective_rng = rng or random.Random(0)
    seq = list(sequence)
    i = 0
    while i < len(seq):
        run_char = seq[i]
        run_end = i + 1
        while run_end < len(seq) and seq[run_end] == run_char:
            run_end += 1
        run_len = run_end - i
        if run_len > max_len:
            insert_pos = i + max_len
            replacement = {
                "A": ["C", "G"],
                "T": ["A", "C"],
                "G": ["A", "T"],
                "C": ["G", "T"],
            }[run_char]
            seq[insert_pos] = effective_rng.choice(replacement)
            run_end = insert_pos + 1
        i = run_end
    return "".join(seq)
