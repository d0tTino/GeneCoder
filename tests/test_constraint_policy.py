from __future__ import annotations

from genecoder.constraints import (
    ConstraintEngine,
    ConstraintPolicy,
    ConstraintRepairPipeline,
    ObjectivePolicy,
    RepairPolicy,
    load_constraint_policy,
)


def test_constraint_policy_roundtrip() -> None:
    policy = ConstraintPolicy(
        min_length=10,
        max_length=20,
        gc_min=0.2,
        gc_max=0.8,
        max_homopolymer=4,
        restriction_site_bans=("GAATTC",),
    )
    clone = load_constraint_policy(policy.to_dict())
    assert clone.to_dict()["restriction_site_bans"] == ["GAATTC"]


def test_constraint_engine_reports_score() -> None:
    policy = ConstraintPolicy(min_length=5, max_length=10, gc_min=0.5, gc_max=0.6, max_homopolymer=2)
    report = ConstraintEngine(policy.to_rule_set()).validate("AAAA")
    assert report.count >= 1
    assert report.score >= 1


def test_constraint_repair_pipeline_ecc_prefix_preserved() -> None:
    policy = ConstraintPolicy(
        min_length=1,
        max_length=20,
        gc_min=0.0,
        gc_max=1.0,
        max_homopolymer=2,
        repair=RepairPolicy(enabled=True, profile="strict", strategy="deterministic", ecc_protected_prefix=2),
    )
    seq = "AATTTT"
    fixed = ConstraintRepairPipeline(policy).run(seq)
    assert fixed.sequence.startswith("AA")


def test_constraint_policy_profile_strategy_resolution() -> None:
    policy = ConstraintPolicy(repair=RepairPolicy(enabled=True, profile="strict"))
    assert policy.strategy_name() == "deterministic"


def test_constraint_engine_validate_batch() -> None:
    policy = ConstraintPolicy(min_length=1, max_length=10, gc_min=0.4, gc_max=0.6, max_homopolymer=3)
    engine = ConstraintEngine(policy.to_rule_set())
    reports = engine.validate_batch(["ACGT", "GGGG"])
    assert len(reports) == 2
    assert reports[0].count == 0
    assert reports[1].count >= 1


def test_constraint_repair_pipeline_repair_batch() -> None:
    policy = ConstraintPolicy(
        min_length=1,
        max_length=20,
        gc_min=0.0,
        gc_max=1.0,
        max_homopolymer=2,
        repair=RepairPolicy(enabled=True, profile="strict", strategy="deterministic"),
    )
    results = ConstraintRepairPipeline(policy).repair_batch(["AATTTT", "CCGG"], stage="encode")
    assert len(results) == 2
    assert results[0].sequence.startswith("AA")
    assert results[0].report_after.count == 0
    assert results[1].report_before.count == 0


def test_constraint_objectives_roundtrip() -> None:
    policy = ConstraintPolicy(objectives=ObjectivePolicy(solver="deterministic", replay_seed=19))
    clone = load_constraint_policy(policy.to_dict())
    assert clone.objectives.solver == "deterministic"
    assert clone.objectives.replay_seed == 19


def test_constraint_repair_pipeline_objective_tradeoff_payload() -> None:
    policy = ConstraintPolicy(
        min_length=1,
        max_length=20,
        gc_min=0.0,
        gc_max=1.0,
        max_homopolymer=2,
        repair=RepairPolicy(enabled=True, profile="balanced", strategy="external_solver"),
        objectives=ObjectivePolicy(solver="deterministic", replay_seed=5),
    )
    result = ConstraintRepairPipeline(policy).run("AATTTT")
    assert result.objective_score is not None
    assert isinstance(result.objective_tradeoff, dict)
    assert "gc_deviation" in (result.objective_tradeoff or {})
