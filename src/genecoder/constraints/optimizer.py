from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Callable

from .policy import ConstraintPolicy


@dataclass(frozen=True)
class OptimizationScore:
    score: float
    objectives: dict[str, float]


@dataclass(frozen=True)
class OptimizationResult:
    sequence: str
    score: float
    objectives: dict[str, float]
    mode: str
    candidate_count: int

    def to_dict(self) -> dict[str, float | int | str | dict[str, float]]:
        return {
            "mode": self.mode,
            "score": self.score,
            "candidate_count": self.candidate_count,
            "objectives": dict(self.objectives),
        }


class ConstraintOptimizer:
    """Score and select candidate encodings under weighted policy objectives."""

    def __init__(self, policy: ConstraintPolicy):
        self.policy = policy

    def score(self, sequence: str) -> OptimizationScore:
        length = max(1, len(sequence))
        gc = sum(1 for base in sequence if base in {"G", "C"}) / length

        max_run = 1
        run = 1
        for i in range(1, len(sequence)):
            if sequence[i] == sequence[i - 1]:
                run += 1
                max_run = max(max_run, run)
            else:
                run = 1

        gc_range_penalty = 0.0
        if gc < self.policy.gc_min:
            gc_range_penalty = self.policy.gc_min - gc
        elif gc > self.policy.gc_max:
            gc_range_penalty = gc - self.policy.gc_max

        restriction_hits = 0
        for motif in self.policy.restriction_site_bans:
            if motif:
                restriction_hits += sequence.count(motif)

        decode_success_proxy = max(
            0.0,
            1.0
            - abs(gc - 0.5)
            - (max(0, max_run - self.policy.max_homopolymer) / length)
            - (restriction_hits / length),
        )
        objectives = {
            "gc_range_penalty": gc_range_penalty,
            "homopolymer_cap_penalty": float(max(0, max_run - self.policy.max_homopolymer)),
            "restriction_site_penalty": float(restriction_hits),
            "decode_success_proxy": decode_success_proxy,
            # Backward-compatible aliases used by older configs/reports.
            "gc_deviation": abs(gc - 0.5),
            "homopolymer_excess": float(max(0, max_run - self.policy.max_homopolymer)),
            "recovery_proxy": decode_success_proxy,
            "redundancy": 1.0,
        }

        total = 0.0
        for term in self.policy.objectives.soft_objectives:
            raw = float(objectives.get(term.key, 0.0))
            if term.goal == "max":
                contribution = -raw
            elif term.goal == "target":
                contribution = abs(raw - float(term.target or 0.0))
            else:
                contribution = raw
            total += float(term.weight) * contribution
        return OptimizationScore(score=total, objectives=objectives)

    def optimize(
        self,
        sequence: str,
        *,
        validate_candidate: Callable[[str], bool] | None = None,
    ) -> OptimizationResult:
        mode = self.policy.objectives.optimization_mode
        if mode != "policy_search":
            baseline = self.score(sequence)
            return OptimizationResult(
                sequence=sequence,
                score=baseline.score,
                objectives=baseline.objectives,
                mode=mode,
                candidate_count=1,
            )

        rng = random.Random(self.policy.objectives.replay_seed)
        candidates = [sequence]
        for _ in range(max(1, self.policy.objectives.search_candidates) - 1):
            chars = list(sequence)
            for _m in range(max(1, self.policy.objectives.search_mutations)):
                if not chars:
                    break
                idx = rng.randrange(len(chars))
                base = chars[idx]
                options = [b for b in "ACGT" if b != base]
                chars[idx] = rng.choice(options)
            candidates.append("".join(chars))

        best_seq = sequence
        best_score = self.score(sequence)
        for candidate in candidates[1:]:
            if validate_candidate is not None and not validate_candidate(candidate):
                continue
            scored = self.score(candidate)
            if scored.score < best_score.score:
                best_seq = candidate
                best_score = scored

        return OptimizationResult(
            sequence=best_seq,
            score=best_score.score,
            objectives=best_score.objectives,
            mode=mode,
            candidate_count=len(candidates),
        )

