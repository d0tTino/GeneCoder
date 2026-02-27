from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .engine import ConstraintEngine
from .policy import ConstraintPolicy
from .report import ConstraintReport, RepairResult
from .solvers import DNAChiselSolverBackend
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

    @property
    def repaired(self) -> bool:
        return self.repair is not None


class ConstraintRepairPipeline:
    def __init__(self, policy: ConstraintPolicy):
        self.policy = policy
        self.engine = ConstraintEngine(policy.to_rule_set())

    def _build_strategy(self) -> DeterministicRepairStrategy | StochasticRepairStrategy | ExternalSolverRepairStrategy:
        strategy_name = self.policy.strategy_name()
        if strategy_name == "deterministic":
            return DeterministicRepairStrategy()
        if strategy_name == "external_solver":
            return ExternalSolverRepairStrategy(solver_backend=DNAChiselSolverBackend())
        return StochasticRepairStrategy()

    def run(self, sequence: str, *, stage: str = "encode") -> RepairPipelineResult:
        before_report = self.engine.validate(sequence)
        if before_report.count == 0:
            return RepairPipelineResult(
                sequence=sequence,
                report_before=before_report,
                report_after=before_report,
                repair=None,
                residual_risk=0.0,
                stage=stage,
            )

        if self.policy.assumption_mode == "fail_fast":
            raise ConstraintStageGateError(
                f"Constraint stage gate '{stage}' failed with {before_report.count} violation(s)"
            )
        if not self.policy.repair.enabled:
            return RepairPipelineResult(
                sequence=sequence,
                report_before=before_report,
                report_after=before_report,
                repair=None,
                residual_risk=before_report.pressure,
                stage=stage,
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
        return RepairPipelineResult(
            sequence=repaired,
            report_before=before_report,
            report_after=after_report,
            repair=repair,
            residual_risk=after_report.pressure,
            stage=stage,
        )

    def repair_batch(self, sequences: Sequence[str], *, stage: str = "encode") -> list[RepairPipelineResult]:
        return [self.run(sequence, stage=stage) for sequence in sequences]

    def validate_batch(self, sequences: Sequence[str]) -> list[ConstraintReport]:
        return self.engine.validate_batch(list(sequences))
