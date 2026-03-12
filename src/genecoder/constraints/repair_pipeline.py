from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .engine import ConstraintEngine
from .optimizer import ConstraintOptimizer
from .policy import ConstraintPolicy
from .report import ConstraintReport, RepairResult
from .solvers import resolve_solver
from .strategies import DeterministicRepairStrategy, ExternalSolverRepairStrategy, StochasticRepairStrategy


class ConstraintStageGateError(ValueError):
    pass


@dataclass
class RepairPipelineResult:
    sequence: str
    report_before: ConstraintReport
    report_after: ConstraintReport
    repair: RepairResult | None
    residual_risk: float
    stage: str = "encode"
    objective_score: float | None = None
    objective_tradeoff: dict[str, object] | None = None

    @property
    def repaired(self) -> bool:
        return self.repair is not None


class ConstraintRepairPipeline:
    def __init__(self, policy: ConstraintPolicy):
        self.policy = policy
        self.engine = ConstraintEngine(policy.to_rule_set())
        self.optimizer = ConstraintOptimizer(policy)

    def _build_strategy(self) -> DeterministicRepairStrategy | StochasticRepairStrategy | ExternalSolverRepairStrategy:
        strategy_name = self.policy.strategy_name()
        solver_name = self.policy.objectives.solver or strategy_name
        if strategy_name == "deterministic":
            return DeterministicRepairStrategy()
        if strategy_name == "external_solver" or solver_name in {"external_solver", "dnachisel"}:
            return ExternalSolverRepairStrategy(
                solver_backend=resolve_solver(solver_name),
                objective_policy=self.policy.objectives,
                replay_seed=self.policy.objectives.replay_seed,
            )
        if solver_name != "stochastic":
            return ExternalSolverRepairStrategy(
                solver_backend=resolve_solver(solver_name),
                objective_policy=self.policy.objectives,
                replay_seed=self.policy.objectives.replay_seed,
                name=solver_name,
            )
        return StochasticRepairStrategy()

    def _objective_score(self, sequence: str) -> tuple[float, dict[str, float]]:
        scored = self.optimizer.score(sequence)
        return scored.score, scored.objectives

    def run(self, sequence: str, *, stage: str = "encode") -> RepairPipelineResult:
        before_report = self.engine.validate(sequence)
        optimized = self.optimizer.optimize(
            sequence,
            validate_candidate=lambda cand: self.engine.validate(cand).count == 0,
        )
        if optimized.mode == "policy_search" and optimized.sequence != sequence and before_report.count == 0:
            sequence = optimized.sequence
            before_report = self.engine.validate(sequence)
        if before_report.count == 0:
            score, values = self._objective_score(sequence)
            values["optimization_mode"] = optimized.mode
            values["candidate_count"] = float(optimized.candidate_count)
            return RepairPipelineResult(
                sequence=sequence,
                report_before=before_report,
                report_after=before_report,
                repair=None,
                residual_risk=0.0,
                stage=stage,
                objective_score=score,
                objective_tradeoff=values,
            )

        if self.policy.assumption_mode == "fail_fast":
            raise ConstraintStageGateError(
                f"Constraint stage gate '{stage}' failed with {before_report.count} violation(s)"
            )
        if not self.policy.repair.enabled:
            score, values = self._objective_score(sequence)
            values["optimization_mode"] = optimized.mode
            values["candidate_count"] = float(optimized.candidate_count)
            return RepairPipelineResult(
                sequence=sequence,
                report_before=before_report,
                report_after=before_report,
                repair=None,
                residual_risk=before_report.pressure,
                stage=stage,
                objective_score=score,
                objective_tradeoff=values,
            )

        prefix = max(0, self.policy.repair.ecc_protected_prefix)
        protected = sequence[:prefix]
        mutable = sequence[prefix:]
        strategy = self._build_strategy()
        _report, repair = self.engine.repair(mutable, strategy)
        repaired = protected + repair.sequence_after
        after_report = self.engine.validate(repaired)
        if after_report.count > 0:
            raise ConstraintStageGateError(
                f"Constraint stage gate '{stage}' still has {after_report.count} residual violation(s) after repair"
            )
        if optimized.mode == "policy_search":
            post = self.optimizer.optimize(
                repaired,
                validate_candidate=lambda cand: self.engine.validate(cand).count == 0,
            )
            repaired = post.sequence
            after_report = self.engine.validate(repaired)
        score, values = self._objective_score(repaired)
        values["optimization_mode"] = optimized.mode
        values["candidate_count"] = float(optimized.candidate_count)
        return RepairPipelineResult(
            sequence=repaired,
            report_before=before_report,
            report_after=after_report,
            repair=repair,
            residual_risk=after_report.pressure,
            stage=stage,
            objective_score=score,
            objective_tradeoff=values,
        )

    def repair_batch(self, sequences: Sequence[str], *, stage: str = "encode") -> list[RepairPipelineResult]:
        return [self.run(sequence, stage=stage) for sequence in sequences]

    def validate_batch(self, sequences: Sequence[str]) -> list[ConstraintReport]:
        return self.engine.validate_batch(list(sequences))
