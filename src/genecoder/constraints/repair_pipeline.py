from __future__ import annotations

from dataclasses import dataclass

from .engine import ConstraintEngine
from .policy import ConstraintPolicy
from .report import RepairResult
from .strategies import DeterministicRepairStrategy, StochasticRepairStrategy


@dataclass
class RepairPipelineResult:
    sequence: str
    repair: RepairResult | None


class ConstraintRepairPipeline:
    def __init__(self, policy: ConstraintPolicy):
        self.policy = policy
        self.engine = ConstraintEngine(policy.to_rule_set())

    def run(self, sequence: str) -> RepairPipelineResult:
        if not self.policy.repair.enabled:
            return RepairPipelineResult(sequence=sequence, repair=None)
        prefix = max(0, self.policy.repair.ecc_protected_prefix)
        protected = sequence[:prefix]
        mutable = sequence[prefix:]
        strategy_name = self.policy.repair.strategy
        if strategy_name == "deterministic":
            strategy = DeterministicRepairStrategy()
        else:
            strategy = StochasticRepairStrategy()
        _report, repair = self.engine.repair(mutable, strategy)
        repaired = protected + repair.sequence_after
        return RepairPipelineResult(sequence=repaired, repair=repair)
