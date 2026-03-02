from __future__ import annotations

import secrets
from typing import Callable

from genecoder.sdk.plugins import Simulator
from genecoder.formats import SequenceBatch
from genecoder.simulators.batch_utils import (
    RESULT_COVERAGE_KEY,
    RESULT_DROPOUT_FLAG_KEY,
    clone_batch,
    finalize_batch_statistics,
)


class PassthroughChannel(Simulator):  # type: ignore[misc]
    """Simple simulator demonstrating the :class:`SequenceBatch` API."""

    supports_batches = True

    def simulate(self, sequence: str | SequenceBatch) -> SequenceBatch:
        batch = self._ensure_batch(sequence)
        mutated = clone_batch(batch)

        coverage_counts: list[int] = []
        dropouts: list[bool] = []
        synthesis_failures: list[bool] = []
        mutation_totals: list[tuple[int, int, int]] = []

        for original, oligo in zip(batch.oligos, mutated.oligos):
            oligo.sequence = original.sequence
            coverage = 1

            coverage_counts.append(coverage)
            dropouts.append(False)
            synthesis_failures.append(False)
            mutation_totals.append((0, 0, 0))

            oligo.metadata[RESULT_COVERAGE_KEY] = str(coverage)
            oligo.metadata[RESULT_DROPOUT_FLAG_KEY] = "false"

        finalize_batch_statistics(
            mutated,
            coverage_counts,
            dropouts,
            synthesis_failures,
            mutation_totals,
        )

        if mutated.seed is None:
            mutated.seed = secrets.randbits(32)
        mutated.metadata["simulator"] = "example"
        mutated.metadata["sim_seed"] = str(mutated.seed)

        return mutated

    def _ensure_batch(self, sequence: str | SequenceBatch) -> SequenceBatch:
        if isinstance(sequence, SequenceBatch):
            return sequence

        batch_seed = secrets.randbits(32)
        return SequenceBatch.build(
            [("example", sequence)],
            batch_id="example",
            batch_seed=batch_seed,
        )


def register(register_simulator: Callable[[str, Simulator], None]) -> None:
    """Register the example simulator."""

    register_simulator("example", PassthroughChannel())
