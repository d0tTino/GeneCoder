from __future__ import annotations

"""Helpers for batch-aware sequencing simulators."""

import json
from collections import Counter
from dataclasses import replace
from difflib import SequenceMatcher
from typing import Any, Callable, Mapping, Sequence

from ..formats import SequenceBatch

CONFIG_DROPOUT_KEY = "sim_dropout_rate"
CONFIG_SYNTHESIS_KEY = "sim_synthesis_loss"
CONFIG_COVERAGE_KEY = "sim_coverage_distribution"

RESULT_COVERAGE_KEY = "sim_coverage"
RESULT_DROPOUT_FLAG_KEY = "sim_dropout"
RESULT_SYNTHESIS_FLAG_KEY = "sim_synthesis_failed"
RESULT_MUTATION_LOG_KEY = "sim_mutation_log"
RESULT_MUTATION_TOTALS_KEY = "sim_mutation_counts"
RESULT_CONSENSUS_TOTALS_KEY = "sim_consensus_counts"

__all__ = [
    "clone_batch",
    "finalize_batch_statistics",
    "mutation_counts",
    "apply_legacy_simulator",
    "bool_to_str",
    "load_coverage_distribution",
    "CONFIG_DROPOUT_KEY",
    "CONFIG_SYNTHESIS_KEY",
    "CONFIG_COVERAGE_KEY",
    "RESULT_COVERAGE_KEY",
    "RESULT_DROPOUT_FLAG_KEY",
    "RESULT_SYNTHESIS_FLAG_KEY",
    "RESULT_MUTATION_LOG_KEY",
    "RESULT_MUTATION_TOTALS_KEY",
    "RESULT_CONSENSUS_TOTALS_KEY",
    "metadata_float",
]


def clone_batch(batch: SequenceBatch) -> SequenceBatch:
    """Return a deep-ish copy of ``batch`` with independent metadata."""

    return SequenceBatch(
        batch_id=batch.batch_id,
        metadata=dict(batch.metadata),
        seed=batch.seed,
        oligos=[replace(oligo, metadata=dict(oligo.metadata)) for oligo in batch.oligos],
        legacy=batch.legacy,
    )


def mutation_counts(original: str, mutated: str) -> tuple[int, int, int]:
    """Return substitution, insertion and deletion counts between two strings."""

    subs = ins = dels = 0
    matcher = SequenceMatcher(None, original, mutated)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            subs += max(i2 - i1, j2 - j1)
        elif tag == "delete":
            dels += i2 - i1
        elif tag == "insert":
            ins += j2 - j1
    return subs, ins, dels


def bool_to_str(value: bool) -> str:
    """Return ``"true"`` or ``"false"`` for ``value``."""

    return "true" if value else "false"


def load_coverage_distribution(
    value: object,
) -> dict[int, float] | None:
    """Parse ``value`` into a coverage distribution mapping."""

    if value in (None, ""):
        return None

    data: object
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
            for chunk in raw.split(","):
                if not chunk:
                    continue
                if ":" in chunk:
                    key, weight = chunk.split(":", 1)
                else:
                    key, weight = chunk, "1"
                try:
                    cov = int(key.strip())
                    wt = float(weight.strip())
                except ValueError:
                    continue
                data[cov] = data.get(cov, 0.0) + wt
    else:
        data = value

    if isinstance(data, Mapping):
        result: dict[int, float] = {}
        for key, weight in data.items():
            try:
                cov = int(key)
                wt = float(weight)
            except (TypeError, ValueError):
                continue
            if wt < 0:
                continue
            result[cov] = result.get(cov, 0.0) + wt
        return result or None

    if isinstance(data, Sequence):
        result: dict[int, float] = {}
        for item in data:
            try:
                cov = int(item)
            except (TypeError, ValueError):
                continue
            result[cov] = result.get(cov, 0.0) + 1.0
        return result or None

    return None


def metadata_float(
    metadata: Mapping[str, Any], key: str, default: float = 0.0
) -> float:
    """Return ``key`` parsed from ``metadata`` as ``float``."""

    value = metadata.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def finalize_batch_statistics(
    batch: SequenceBatch,
    coverage: Sequence[int],
    dropouts: Sequence[bool],
    synthesis_failures: Sequence[bool],
    per_oligo_counts: Sequence[tuple[int, int, int]],
) -> None:
    """Augment ``batch`` metadata with aggregate statistics."""

    total = len(coverage) or 1
    histogram = Counter(int(c) for c in coverage)
    batch.metadata["sim_coverage_histogram"] = json.dumps(
        {str(k): histogram[k] for k in sorted(histogram)}
    )
    batch.metadata["sim_total_reads"] = str(sum(int(c) for c in coverage))
    batch.metadata["sim_average_coverage"] = (
        f"{(sum(float(c) for c in coverage) / total):.6f}"
    )
    dropout_total = sum(1 for flag in dropouts if flag)
    batch.metadata["sim_dropout_total"] = str(dropout_total)
    batch.metadata["sim_dropout_fraction"] = f"{(dropout_total / total):.6f}"
    synth_total = sum(1 for flag in synthesis_failures if flag)
    batch.metadata["sim_synthesis_failures"] = str(synth_total)
    batch.metadata["sim_synthesis_fraction"] = f"{(synth_total / total):.6f}"
    batch.metadata["sim_mutation_totals"] = json.dumps(
        {
            "substitutions": sum(item[0] for item in per_oligo_counts),
            "insertions": sum(item[1] for item in per_oligo_counts),
            "deletions": sum(item[2] for item in per_oligo_counts),
        }
    )


def apply_legacy_simulator(
    batch: SequenceBatch, simulate_fn: Callable[[str], str]
) -> SequenceBatch:
    """Return ``batch`` processed by a legacy string-based simulator."""

    mutated = clone_batch(batch)

    coverage_counts: list[int] = []
    dropout_flags: list[bool] = []
    synthesis_flags: list[bool] = []
    consensus_totals: list[tuple[int, int, int]] = []

    for original, oligo in zip(batch.oligos, mutated.oligos):
        result = simulate_fn(original.sequence)
        if not isinstance(result, str):
            raise TypeError(
                "legacy simulator must return a string when given a string input"
            )

        dropped = result == ""
        coverage = 0 if dropped else 1
        oligo.sequence = result

        if dropped:
            mutation_log: list[dict[str, int | str]] = []
            mutation_totals = {"substitutions": 0, "insertions": 0, "deletions": 0}
            consensus_counts = (0, 0, 0)
        else:
            sub, ins, dele = mutation_counts(original.sequence, result)
            mutation_log = [
                {
                    "read": result,
                    "substitutions": sub,
                    "insertions": ins,
                    "deletions": dele,
                }
            ]
            mutation_totals = {
                "substitutions": sub,
                "insertions": ins,
                "deletions": dele,
            }
            consensus_counts = (sub, ins, dele)

        oligo.metadata[RESULT_COVERAGE_KEY] = str(coverage)
        oligo.metadata[RESULT_DROPOUT_FLAG_KEY] = bool_to_str(dropped)
        oligo.metadata[RESULT_SYNTHESIS_FLAG_KEY] = bool_to_str(False)
        oligo.metadata[RESULT_MUTATION_LOG_KEY] = json.dumps(mutation_log)
        oligo.metadata[RESULT_MUTATION_TOTALS_KEY] = json.dumps(mutation_totals)
        oligo.metadata[RESULT_CONSENSUS_TOTALS_KEY] = json.dumps(
            {
                "substitutions": consensus_counts[0],
                "insertions": consensus_counts[1],
                "deletions": consensus_counts[2],
            }
        )

        coverage_counts.append(coverage)
        dropout_flags.append(dropped)
        synthesis_flags.append(False)
        consensus_totals.append(consensus_counts)

    finalize_batch_statistics(
        mutated, coverage_counts, dropout_flags, synthesis_flags, consensus_totals
    )
    return mutated
