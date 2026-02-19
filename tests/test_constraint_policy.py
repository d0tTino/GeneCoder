from __future__ import annotations

from genecoder.constraints import ConstraintEngine, ConstraintPolicy, ConstraintRepairPipeline, RepairPolicy, load_constraint_policy


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
