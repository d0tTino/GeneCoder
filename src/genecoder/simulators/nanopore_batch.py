"""Batch mutation helpers for the Nanopore simulators."""

from __future__ import annotations

import json
import random
from typing import Dict, Iterable, Protocol, Sequence, Tuple

try:  # Optional at runtime
    from numba import njit
except Exception:  # pragma: no cover - fallback when numba missing
    from typing import Callable, ParamSpec, TypeVar

    P = ParamSpec("P")
    R = TypeVar("R")

    def njit(*args: object, **kwargs: object) -> Callable[[Callable[P, R]], Callable[P, R]]:
        def wrapper(func: Callable[P, R]) -> Callable[P, R]:
            return func

        return wrapper

from ..error_simulation import NUCLEOTIDES, _random_substitution
from ..formats import SequenceBatch
from ..random_utils import make_rng
from .batch_utils import (
    CONFIG_COVERAGE_KEY,
    CONFIG_DROPOUT_KEY,
    CONFIG_SYNTHESIS_KEY,
    RESULT_CONSENSUS_TOTALS_KEY,
    RESULT_COVERAGE_KEY,
    RESULT_DROPOUT_FLAG_KEY,
    RESULT_MUTATION_LOG_KEY,
    RESULT_MUTATION_TOTALS_KEY,
    RESULT_SYNTHESIS_FLAG_KEY,
    bool_to_str,
    clone_batch,
    finalize_batch_statistics,
    load_coverage_distribution,
    metadata_float,
    mutation_counts,
)

__all__ = [
    "NanoporeBatchProtocol",
    "mutate_read_jit",
    "mutate_read",
    "consensus",
    "simulate_batch",
]


class NanoporeBatchProtocol(Protocol):
    """Protocol describing the batch interface of ``NanoporeChannel``."""

    substitution_rate: float
    insertion_rate: float
    deletion_rate: float
    coverage: float
    context_errors: Dict[str, float]
    context_insertions: Dict[str, Dict[int, float]]
    context_deletions: Dict[str, Dict[int, float]]
    insertion_profile: Dict[int, float]
    deletion_profile: Dict[int, float]
    quality_profile: Sequence[float] | None

    def get_coverage(self, sequence: str) -> float: ...

    def _simulate_base_read(self, sequence: str, rng: random.Random) -> str: ...

    def _mutate_observed_read(
        self, original: str, base_read: str, rng: random.Random
    ) -> str: ...


@njit(cache=True, forceobj=True)  # type: ignore[misc]
def mutate_read_jit(
    read: str,
    quality: Sequence[float] | None,
    rng: random.Random,
    substitution_rate: float,
    insertion_rate: float,
    deletion_rate: float,
    context_errors: Dict[str, float],
    insertion_profile: Dict[int, float],
    deletion_profile: Dict[int, float],
    context_insertions: Dict[str, Dict[int, float]],
    context_deletions: Dict[str, Dict[int, float]],
) -> str:
    mutated: list[str] = []
    prev = ""
    run_len = 0

    for idx, nt in enumerate(read):
        if nt == prev:
            run_len += 1
        else:
            run_len = 1
            prev = nt

        context = read[idx - 1 : idx + 1].upper() if idx > 0 else ""

        del_p = deletion_profile.get(run_len, deletion_rate)
        if context_deletions and context:
            ctx_profile = context_deletions.get(context)
            if ctx_profile is not None:
                del_p = ctx_profile.get(run_len, ctx_profile.get(1, del_p))
        del_p = min(1.0, del_p)
        if rng.random() < del_p:
            continue

        sub_p = (
            quality[idx] if quality is not None and idx < len(quality) else substitution_rate
        )
        if context_errors and context:
            sub_p *= context_errors.get(context, 1.0)

        if rng.random() < sub_p:
            nt = _random_substitution(nt, rng)

        mutated.append(nt)
        ins_p = insertion_profile.get(run_len, insertion_rate)
        if context_insertions and context:
            ctx_profile = context_insertions.get(context)
            if ctx_profile is not None:
                ins_p = ctx_profile.get(run_len, ctx_profile.get(1, ins_p))
        if rng.random() < ins_p:
            mutated.append(rng.choice(NUCLEOTIDES))

    return "".join(mutated)


def mutate_read(
    read: str,
    quality: Sequence[float] | None,
    rng: random.Random,
    channel: NanoporeBatchProtocol,
) -> str:
    """Mutate ``read`` using the provided ``channel`` parameters."""

    from typing import cast

    return cast(
        str,
        mutate_read_jit(
            read,
            quality,
            rng,
            channel.substitution_rate,
            channel.insertion_rate,
            channel.deletion_rate,
            channel.context_errors,
            channel.insertion_profile,
            channel.deletion_profile,
            channel.context_insertions,
            channel.context_deletions,
        ),
    )


def consensus(reads: Iterable[str]) -> str:
    """Return the majority consensus sequence for ``reads``."""

    reads = list(reads)
    if not reads:
        return ""
    length = max(len(r) for r in reads)
    result: list[str] = []
    for i in range(length):
        counts: Dict[str, int] = {}
        for r in reads:
            if i < len(r):
                base = r[i]
                counts[base] = counts.get(base, 0) + 1
        if counts:
            result.append(max(counts, key=lambda k: counts[k]))
    return "".join(result)


def _select_coverage(
    channel_rng: random.Random,
    coverage_dist: Dict[int, float] | None,
    default_coverage: float,
) -> tuple[int, bool]:
    if coverage_dist:
        total_weight = sum(coverage_dist.values())
        threshold = channel_rng.random() * total_weight if total_weight > 0 else 0.0
        cumulative = 0.0
        coverage_choice = 0
        for cov, weight in sorted(coverage_dist.items()):
            cumulative += weight
            coverage_choice = int(cov)
            if threshold <= cumulative:
                break
        coverage = max(0, coverage_choice)
    else:
        coverage = max(1, int(default_coverage))
    return coverage, coverage <= 0


def simulate_batch(
    channel: NanoporeBatchProtocol,
    batch: SequenceBatch,
) -> SequenceBatch:
    """Simulate a batch of sequences for ``channel``."""

    rng = make_rng()
    mutated = clone_batch(batch)
    dropout_rate = metadata_float(mutated.metadata, CONFIG_DROPOUT_KEY, 0.0)
    synthesis_loss = metadata_float(mutated.metadata, CONFIG_SYNTHESIS_KEY, 0.0)
    coverage_dist = load_coverage_distribution(mutated.metadata.get(CONFIG_COVERAGE_KEY))

    coverage_counts: list[int] = []
    dropout_flags: list[bool] = []
    synthesis_flags: list[bool] = []
    consensus_totals: list[Tuple[int, int, int]] = []

    for original, oligo in zip(batch.oligos, mutated.oligos):
        seed = oligo.seed if oligo.seed is not None else int(rng.random() * (2**32 - 1))
        oligo_rng = random.Random(seed)

        dropped = False
        synth_failed = False
        coverage = 0
        read_logs: list[dict[str, int | str]] = []
        per_read_totals = [0, 0, 0]

        if oligo_rng.random() < synthesis_loss:
            synth_failed = True
        elif oligo_rng.random() < dropout_rate:
            dropped = True

        if not dropped and not synth_failed:
            coverage_guess = channel.get_coverage(original.sequence)
            coverage, dropped = _select_coverage(
                oligo_rng, coverage_dist, coverage_guess
            )

        reads: list[str] = []
        if not dropped and not synth_failed:
            for _ in range(coverage):
                base_read = channel._simulate_base_read(original.sequence, oligo_rng)
                mutated_read = channel._mutate_observed_read(
                    original.sequence, base_read, oligo_rng
                )
                reads.append(mutated_read)
                sub, ins, dele = mutation_counts(original.sequence, mutated_read)
                per_read_totals[0] += sub
                per_read_totals[1] += ins
                per_read_totals[2] += dele
                read_logs.append(
                    {
                        "read": mutated_read,
                        "substitutions": sub,
                        "insertions": ins,
                        "deletions": dele,
                    }
                )

        consensus_counts = (0, 0, 0)
        if reads:
            consensus_read = reads[0] if len(reads) == 1 else consensus(reads)
            oligo.sequence = consensus_read
            consensus_counts = mutation_counts(original.sequence, consensus_read)
        else:
            oligo.sequence = ""
            coverage = 0

        oligo.metadata[RESULT_COVERAGE_KEY] = str(coverage)
        oligo.metadata[RESULT_DROPOUT_FLAG_KEY] = bool_to_str(dropped)
        oligo.metadata[RESULT_SYNTHESIS_FLAG_KEY] = bool_to_str(synth_failed)
        oligo.metadata[RESULT_MUTATION_LOG_KEY] = json.dumps(read_logs)
        oligo.metadata[RESULT_MUTATION_TOTALS_KEY] = json.dumps(
            {
                "substitutions": per_read_totals[0],
                "insertions": per_read_totals[1],
                "deletions": per_read_totals[2],
            }
        )
        oligo.metadata[RESULT_CONSENSUS_TOTALS_KEY] = json.dumps(
            {
                "substitutions": consensus_counts[0],
                "insertions": consensus_counts[1],
                "deletions": consensus_counts[2],
            }
        )

        coverage_counts.append(int(coverage))
        dropout_flags.append(dropped)
        synthesis_flags.append(synth_failed)
        consensus_totals.append(consensus_counts)

    finalize_batch_statistics(
        mutated, coverage_counts, dropout_flags, synthesis_flags, consensus_totals
    )
    return mutated

