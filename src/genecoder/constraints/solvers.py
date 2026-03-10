from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Protocol

from .policy import ObjectivePolicy
from .report import RepairResult, build_diff_changes
from .rules import ConstraintRuleSet, GcRangeRule, HomopolymerMaxRule, MotifDenyRule
from .strategies import _adjust_gc, _limit_homopolymers

try:  # optional dependency
    from dnachisel import AvoidPattern, DnaOptimizationProblem, EnforceGCContent
except Exception:  # pragma: no cover
    AvoidPattern = None
    DnaOptimizationProblem = None
    EnforceGCContent = None


class ObjectiveSolver(Protocol):
    name: str

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


@dataclass
class GreedyObjectiveSolver:
    name: str = "deterministic"

    def solve(
        self,
        sequence: str,
        rules: ConstraintRuleSet,
        *,
        strategy_name: str,
        objective_policy: ObjectivePolicy | None = None,
        replay_seed: int | None = None,
    ) -> RepairResult:
        seq = sequence.upper()
        before = seq
        rng = random.Random(replay_seed if replay_seed is not None else 0)
        for rule in rules.rules:
            if isinstance(rule, HomopolymerMaxRule):
                seq = _limit_homopolymers(seq, rule.max_homopolymer, rng=rng)
            elif isinstance(rule, GcRangeRule):
                seq = _adjust_gc(seq, rule.gc_min, rule.gc_max, rng=rng)
        changes = build_diff_changes(before, seq, reason="greedy_objective")
        return RepairResult(
            strategy=strategy_name,
            sequence_before=before,
            sequence_after=seq,
            changes=changes,
            reason="Solved objective policy via greedy deterministic solver",
            metadata={
                "solver": self.name,
                "replay_seed": replay_seed,
                "objective_policy": objective_policy.to_dict() if objective_policy else {},
            },
        )


@dataclass
class DNAChiselSolverBackend:
    name: str = "dnachisel"

    def solve(
        self,
        sequence: str,
        rules: ConstraintRuleSet,
        *,
        strategy_name: str,
        objective_policy: ObjectivePolicy | None = None,
        replay_seed: int | None = None,
    ) -> RepairResult:
        if DnaOptimizationProblem is None:
            raise ImportError("dnachisel is required for DNAChiselSolverBackend")

        constraints = []
        for rule in rules.rules:
            if isinstance(rule, GcRangeRule):
                constraints.append(EnforceGCContent(mini=rule.gc_min, maxi=rule.gc_max))
            elif isinstance(rule, HomopolymerMaxRule):
                for base in "ATGC":
                    constraints.append(AvoidPattern(base * (rule.max_homopolymer + 1)))
            elif isinstance(rule, MotifDenyRule):
                for motif in rule.motifs:
                    constraints.append(AvoidPattern(motif))

        before = sequence.upper()
        problem = DnaOptimizationProblem(sequence=before, constraints=constraints, logger=None)
        problem.resolve_constraints()
        after = str(problem.sequence)
        changes = build_diff_changes(before, after, reason="dnachisel_solver")
        return RepairResult(
            strategy=strategy_name,
            sequence_before=before,
            sequence_after=after,
            changes=changes,
            reason="Solved constraints via DNAChisel backend",
            metadata={
                "backend": self.name,
                "replay_seed": replay_seed,
                "objective_policy": objective_policy.to_dict() if objective_policy else {},
            },
        )


SOLVER_REGISTRY: dict[str, ObjectiveSolver] = {
    "deterministic": GreedyObjectiveSolver(name="deterministic"),
    "stochastic": GreedyObjectiveSolver(name="stochastic"),
    "external_solver": DNAChiselSolverBackend(name="dnachisel"),
    "dnachisel": DNAChiselSolverBackend(name="dnachisel"),
}


def resolve_solver(name: str) -> ObjectiveSolver:
    return SOLVER_REGISTRY.get(name, SOLVER_REGISTRY["deterministic"])
