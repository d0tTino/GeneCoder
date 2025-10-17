"""Batch simulation pipeline for the Illumina channel."""
from __future__ import annotations

from typing import Dict, Protocol, Sequence
import json
import random

from ...formats import SequenceBatch
from ...random_utils import make_rng
from ..batch_utils import (
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
from .mutations import mutate_read
from .utils import consensus, poisson


__all__ = ["simulate_batch"]


class _IlluminaLike(Protocol):
    substitution_rate: float
    insertion_rate: float
    deletion_rate: float
    coverage: float
    read_length: int
    context_errors: Dict[str, float]

    def get_read_length(self, sequence: str) -> int:
        ...

    def get_quality_profile(
        self, sequence: str, read_length: int
    ) -> Sequence[float] | None:
        ...


def _choose_coverage(
    rng: random.Random,
    coverage: float,
    coverage_dist: Dict[int, float] | None,
) -> int:
    if coverage_dist:
        total_weight = sum(coverage_dist.values())
        threshold = rng.random() * total_weight if total_weight > 0 else 0.0
        cumulative = 0.0
        coverage_choice = 0
        for cov, weight in sorted(coverage_dist.items()):
            cumulative += weight
            coverage_choice = int(cov)
            if threshold <= cumulative:
                break
        return max(0, coverage_choice)
    return max(1, poisson(coverage, rng))


def simulate_batch(channel: _IlluminaLike, batch: SequenceBatch) -> SequenceBatch:
    """Return a mutated batch using the Illumina error model."""

    rng = make_rng()
    mutated = clone_batch(batch)
    dropout_rate = metadata_float(mutated.metadata, CONFIG_DROPOUT_KEY, 0.0)
    synthesis_loss = metadata_float(mutated.metadata, CONFIG_SYNTHESIS_KEY, 0.0)
    coverage_dist = load_coverage_distribution(mutated.metadata.get(CONFIG_COVERAGE_KEY))

    coverage_counts: list[int] = []
    dropout_flags: list[bool] = []
    synthesis_flags: list[bool] = []
    consensus_totals: list[tuple[int, int, int]] = []

    for original, oligo in zip(batch.oligos, mutated.oligos):
        seed = (
            oligo.seed if oligo.seed is not None else int(rng.random() * (2**32 - 1))
        )
        oligo_rng = random.Random(seed)

        dropped = False
        synth_failed = False
        coverage_count = 0
        read_logs: list[dict[str, int | str]] = []
        per_read_totals = [0, 0, 0]
        read_length = channel.get_read_length(original.sequence)
        read = original.sequence[:read_length]
        quality = channel.get_quality_profile(original.sequence, read_length)

        if oligo_rng.random() < synthesis_loss:
            synth_failed = True
        elif oligo_rng.random() < dropout_rate:
            dropped = True

        if not dropped and not synth_failed:
            coverage_count = _choose_coverage(oligo_rng, channel.coverage, coverage_dist)
            if coverage_count <= 0:
                dropped = True

        reads: list[str] = []
        if not dropped and not synth_failed:
            for _ in range(coverage_count):
                mutated_read = mutate_read(
                    read,
                    quality,
                    oligo_rng,
                    substitution_rate=channel.substitution_rate,
                    insertion_rate=channel.insertion_rate,
                    deletion_rate=channel.deletion_rate,
                    context_errors=channel.context_errors,
                )
                reads.append(mutated_read)
                sub, ins, dele = mutation_counts(read, mutated_read)
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
            consensus_counts = mutation_counts(read[: len(consensus_read)], consensus_read)
        else:
            oligo.sequence = ""
            coverage_count = 0

        oligo.metadata[RESULT_COVERAGE_KEY] = str(coverage_count)
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

        coverage_counts.append(int(coverage_count))
        dropout_flags.append(dropped)
        synthesis_flags.append(synth_failed)
        consensus_totals.append(consensus_counts)

    finalize_batch_statistics(
        mutated, coverage_counts, dropout_flags, synthesis_flags, consensus_totals
    )
    return mutated
