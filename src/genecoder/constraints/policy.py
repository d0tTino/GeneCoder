from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
import json

from .rules import (
    ConstraintRuleSet,
    GcRangeRule,
    HomopolymerMaxRule,
    LengthRule,
    MotifAllowRule,
    MotifDenyRule,
)


@dataclass(frozen=True)
class RepairPolicy:
    enabled: bool = False
    profile: str = "balanced"
    strategy: str | None = None
    ecc_protected_prefix: int = 0


@dataclass(frozen=True)
class ObjectiveTerm:
    key: str
    weight: float = 1.0
    goal: str = "min"
    target: float | None = None

    def validate(self) -> None:
        if self.goal not in {"min", "max", "target"}:
            raise ValueError("objective term goal must be 'min', 'max', or 'target'")
        if self.goal == "target" and self.target is None:
            raise ValueError("target objective requires target value")


@dataclass(frozen=True)
class ObjectivePolicy:
    hard_constraints: tuple[str, ...] = ("length", "gc", "homopolymer")
    soft_objectives: tuple[ObjectiveTerm, ...] = field(
        default_factory=lambda: (
            ObjectiveTerm(key="gc_deviation", weight=1.0, goal="min", target=0.5),
            ObjectiveTerm(key="homopolymer_excess", weight=1.0, goal="min", target=0.0),
            ObjectiveTerm(key="redundancy", weight=0.2, goal="min", target=1.0),
            ObjectiveTerm(key="recovery_proxy", weight=0.6, goal="max"),
        )
    )
    solver: str = "deterministic"
    replay_seed: int = 0

    def validate(self) -> None:
        if not self.hard_constraints:
            raise ValueError("hard_constraints cannot be empty")
        for term in self.soft_objectives:
            term.validate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "hard_constraints": list(self.hard_constraints),
            "soft_objectives": [
                {"key": term.key, "weight": term.weight, "goal": term.goal, "target": term.target}
                for term in self.soft_objectives
            ],
            "solver": self.solver,
            "replay_seed": self.replay_seed,
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "ObjectivePolicy":
        src = dict(data or {})
        terms_raw = src.get("soft_objectives") if isinstance(src.get("soft_objectives"), list) else None
        terms = []
        if terms_raw is not None:
            for item in terms_raw:
                if not isinstance(item, Mapping):
                    continue
                terms.append(
                    ObjectiveTerm(
                        key=str(item.get("key", "")),
                        weight=float(item.get("weight", 1.0)),
                        goal=str(item.get("goal", "min")),
                        target=(float(item["target"]) if item.get("target") is not None else None),
                    )
                )
        objective = cls(
            hard_constraints=tuple(str(v) for v in src.get("hard_constraints", ("length", "gc", "homopolymer"))),
            soft_objectives=tuple(terms) if terms else cls().soft_objectives,
            solver=str(src.get("solver", "deterministic")),
            replay_seed=int(src.get("replay_seed", 0)),
        )
        objective.validate()
        return objective


@dataclass(frozen=True)
class ConstraintPolicy:
    min_length: int = 25
    max_length: int = 300
    gc_min: float = 0.45
    gc_max: float = 0.55
    max_homopolymer: int = 3
    restriction_site_bans: tuple[str, ...] = ()
    required_motifs: tuple[str, ...] = ()
    repair: RepairPolicy = field(default_factory=RepairPolicy)
    assumption_mode: str = "repair"
    objectives: ObjectivePolicy = field(default_factory=ObjectivePolicy)

    def validate(self) -> None:
        if self.min_length <= 0 or self.max_length <= 0:
            raise ValueError("length window must be positive")
        if self.min_length > self.max_length:
            raise ValueError("min_length cannot exceed max_length")
        if not 0 <= self.gc_min <= 1 or not 0 <= self.gc_max <= 1:
            raise ValueError("gc_min/gc_max must be between 0 and 1")
        if self.gc_min > self.gc_max:
            raise ValueError("gc_min cannot exceed gc_max")
        if self.max_homopolymer < 1:
            raise ValueError("max_homopolymer must be >=1")
        if self.repair.ecc_protected_prefix < 0:
            raise ValueError("ecc_protected_prefix must be >=0")
        if self.assumption_mode not in {"fail_fast", "repair"}:
            raise ValueError("assumption_mode must be 'fail_fast' or 'repair'")
        self.objectives.validate()

    def strategy_name(self) -> str:
        if self.repair.strategy:
            return self.repair.strategy
        profile_map = {
            "strict": "deterministic",
            "deterministic": "deterministic",
            "balanced": "stochastic",
            "exploratory": "stochastic",
            "solver": "external_solver",
        }
        return profile_map.get(self.repair.profile, "stochastic")

    def to_rule_set(self) -> ConstraintRuleSet:
        rules = [
            LengthRule(min_length=self.min_length, max_length=self.max_length),
            GcRangeRule(gc_min=self.gc_min, gc_max=self.gc_max),
            HomopolymerMaxRule(max_homopolymer=self.max_homopolymer),
        ]
        if self.restriction_site_bans:
            rules.append(MotifDenyRule(motifs=self.restriction_site_bans, rule_id="restriction_site_ban"))
        if self.required_motifs:
            rules.append(MotifAllowRule(motifs=self.required_motifs, rule_id="required_motif"))
        return ConstraintRuleSet(rules=rules)

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_length": self.min_length,
            "max_length": self.max_length,
            "gc_min": self.gc_min,
            "gc_max": self.gc_max,
            "max_homopolymer": self.max_homopolymer,
            "restriction_site_bans": list(self.restriction_site_bans),
            "required_motifs": list(self.required_motifs),
            "repair": {
                "enabled": self.repair.enabled,
                "profile": self.repair.profile,
                "strategy": self.repair.strategy,
                "ecc_protected_prefix": self.repair.ecc_protected_prefix,
            },
            "assumption_mode": self.assumption_mode,
            "objectives": self.objectives.to_dict(),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "ConstraintPolicy":
        src = dict(data or {})
        repair_raw = src.get("repair") if isinstance(src.get("repair"), Mapping) else {}
        policy = cls(
            min_length=int(src.get("min_length", 25)),
            max_length=int(src.get("max_length", 300)),
            gc_min=float(src.get("gc_min", 0.45)),
            gc_max=float(src.get("gc_max", 0.55)),
            max_homopolymer=int(src.get("max_homopolymer", 3)),
            restriction_site_bans=tuple(str(x) for x in src.get("restriction_site_bans", src.get("deny_motifs", [])) or ()),
            required_motifs=tuple(str(x) for x in src.get("required_motifs", src.get("allow_motifs", [])) or ()),
            repair=RepairPolicy(
                enabled=bool(repair_raw.get("enabled", False)),
                profile=str(repair_raw.get("profile", "balanced")),
                strategy=(str(repair_raw["strategy"]) if repair_raw.get("strategy") is not None else None),
                ecc_protected_prefix=int(repair_raw.get("ecc_protected_prefix", 0)),
            ),
            assumption_mode=str(src.get("assumption_mode", "repair")),
            objectives=ObjectivePolicy.from_mapping(
                src.get("objectives") if isinstance(src.get("objectives"), Mapping) else None
            ),
        )
        policy.validate()
        return policy


def load_constraint_policy(source: str | Path | Mapping[str, Any] | None, *, fallback: Mapping[str, Any] | None = None) -> ConstraintPolicy:
    if source is None:
        merged = dict(fallback or {})
        return ConstraintPolicy.from_mapping(merged)
    if isinstance(source, Mapping):
        merged = dict(fallback or {})
        merged.update(dict(source))
        return ConstraintPolicy.from_mapping(merged)

    path = Path(source)
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        import yaml

        payload = yaml.safe_load(text)
    if not isinstance(payload, Mapping):
        raise ValueError("Constraint policy file must contain a mapping")
    merged = dict(fallback or {})
    merged.update(dict(payload))
    return ConstraintPolicy.from_mapping(merged)
