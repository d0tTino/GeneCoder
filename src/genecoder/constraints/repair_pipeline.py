from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .engine import ConstraintEngine
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
        length = len(sequence)
        gc = (sum(1 for b in sequence if b in {"G", "C"}) / length) if length else 0.0
        max_run = 1
        run = 1
        for i in range(1, len(sequence)):
            if sequence[i] == sequence[i - 1]:
                run += 1
                max_run = max(max_run, run)
            else:
                run = 1
        values = {
            "gc_deviation": abs(gc - 0.5),
            "homopolymer_excess": max(0.0, float(max_run - self.policy.max_homopolymer)),
            "redundancy": 1.0,
            "recovery_proxy": max(0.0, 1.0 - abs(gc - 0.5) - (max_run / max(1, length))),
        }
        score = 0.0
        for term in self.policy.objectives.soft_objectives:
            raw = values.get(term.key, 0.0)
            if term.goal == "max":
                contribution = -raw
            elif term.goal == "target":
                contribution = abs(raw - float(term.target or 0.0))
            else:
                contribution = raw
            score += float(term.weight) * contribution
        return score, values

    def run(self, sequence: str, *, stage: str = "encode") -> RepairPipelineResult:
        before_report = self.engine.validate(sequence)
        if before_report.count == 0:
            score, values = self._objective_score(sequence)
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
        score, values = self._objective_score(repaired)
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
