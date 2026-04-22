from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from genecoder.constraints import ConstraintPolicy, ConstraintRepairPipeline, load_constraint_policy
from genecoder.runtime.models import ConstraintStageInput, ConstraintStageOutput


def resolve_constraint_policy(raw: Mapping[str, Any] | None) -> ConstraintPolicy | None:
    if not raw:
        return None
    policy_raw = raw.get("constraint_policy")
    if policy_raw is None:
        return None
    if isinstance(policy_raw, ConstraintPolicy):
        return policy_raw
    if isinstance(policy_raw, Mapping):
        return load_constraint_policy(policy_raw)
    return None


class ConstraintStageService:
    def run(self, payload: ConstraintStageInput) -> ConstraintStageOutput:
        pipeline = ConstraintRepairPipeline(payload.policy)
        primaries = payload.batch.primary_oligos() or payload.batch.oligos
        outcomes = pipeline.repair_batch([ol.sequence for ol in primaries], stage=payload.stage)
        by_oligo: dict[str, dict[str, Any]] = {}
        for idx, (oligo, outcome) in enumerate(zip(primaries, outcomes), start=1):
            if outcome.sequence != oligo.sequence:
                oligo.sequence = outcome.sequence
            key = str(
                oligo.metadata.get("oligo_id")
                or oligo.oligo_id
                or oligo.metadata.get("oligo_index")
                or idx
            )
            by_oligo[key] = {
                "oligo_index": idx,
                "violations_before": outcome.report_before.count,
                "violations_after": outcome.report_after.count,
                "pressure_before": outcome.report_before.pressure,
                "pressure_after": outcome.report_after.pressure,
                "repair_strategy": outcome.repair.strategy if outcome.repair is not None else None,
                "repairs_applied": len(outcome.repair.changes) if outcome.repair is not None else 0,
                "residual_risk": outcome.residual_risk,
                "objective_score": outcome.objective_score,
                "objective_tradeoff": dict(outcome.objective_tradeoff or {}),
                "stage": outcome.stage,
            }

        result = {
            "stage": payload.stage,
            "violations": {
                "before": sum(item.report_before.count for item in outcomes),
                "after": sum(item.report_after.count for item in outcomes),
                "pressure_before": (
                    sum(item.report_before.pressure for item in outcomes) / len(outcomes)
                    if outcomes
                    else 0.0
                ),
                "pressure_after": (
                    sum(item.report_after.pressure for item in outcomes) / len(outcomes)
                    if outcomes
                    else 0.0
                ),
            },
            "repairs_applied": sum(len(item.repair.changes) if item.repair is not None else 0 for item in outcomes),
            "repair_strategy": (
                outcomes[0].repair.strategy if outcomes and outcomes[0].repair is not None else None
            ),
            "residual_risk": (
                sum(item.residual_risk for item in outcomes) / len(outcomes) if outcomes else 0.0
            ),
            "objective_score": (
                sum(float(item.objective_score or 0.0) for item in outcomes) / len(outcomes)
                if outcomes
                else None
            ),
            "objective_tradeoff": {
                "gc": (sum(float((item.objective_tradeoff or {}).get("gc_deviation", 0.0)) for item in outcomes) / len(outcomes)) if outcomes else 0.0,
                "homopolymer": (sum(float((item.objective_tradeoff or {}).get("homopolymer_excess", 0.0)) for item in outcomes) / len(outcomes)) if outcomes else 0.0,
                "redundancy": (sum(float((item.objective_tradeoff or {}).get("redundancy", 0.0)) for item in outcomes) / len(outcomes)) if outcomes else 0.0,
                "recovery": (sum(float((item.objective_tradeoff or {}).get("recovery_proxy", 0.0)) for item in outcomes) / len(outcomes)) if outcomes else 0.0,
            },
            "by_oligo": by_oligo,
        }
        return ConstraintStageOutput(payload=result)
