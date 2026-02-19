from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .report import ConstraintReport, RepairResult
from .rules import ConstraintRuleSet
from .strategies import RepairStrategy


@dataclass
class ConstraintEngine:
    rules: ConstraintRuleSet

    def validate(self, sequence: str) -> ConstraintReport:
        return ConstraintReport(
            sequence=sequence,
            violations=self.rules.validate(sequence),
            score=self.rules.score(sequence),
        )

    def repair(self, sequence: str, strategy: RepairStrategy) -> tuple[ConstraintReport, RepairResult]:
        repair_result = strategy.repair(sequence, self.rules)
        report = self.validate(repair_result.sequence_after)
        return report, repair_result

    def as_manifest_report(self, sequence: str) -> dict[str, object]:
        report = self.validate(sequence)
        counts = Counter(v.rule_id for v in report.violations)
        return {
            "count": report.count,
            "pressure": report.pressure,
            "type_counts": dict(counts),
            "violations": [
                {
                    "type": violation.rule_id,
                    "message": violation.message,
                    "severity": violation.severity,
                    "location": (
                        {"start": violation.location.start, "end": violation.location.end}
                        if violation.location
                        else None
                    ),
                    "details": violation.details,
                }
                for violation in report.violations
            ],
            "limits": self.rules.limits(),
        }
