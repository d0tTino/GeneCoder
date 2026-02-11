from __future__ import annotations

from dataclasses import dataclass

from .report import RepairResult, build_diff_changes
from .rules import ConstraintRuleSet, GcRangeRule, HomopolymerMaxRule, MotifDenyRule

try:  # optional dependency
    from dnachisel import AvoidPattern, DnaOptimizationProblem, EnforceGCContent
except Exception:  # pragma: no cover
    AvoidPattern = None
    DnaOptimizationProblem = None
    EnforceGCContent = None


@dataclass
class DNAChiselSolverBackend:
    name: str = "dnachisel"

    def solve(self, sequence: str, rules: ConstraintRuleSet, *, strategy_name: str) -> RepairResult:
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
            metadata={"backend": self.name},
        )
