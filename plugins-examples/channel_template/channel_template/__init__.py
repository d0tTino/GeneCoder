from __future__ import annotations

import secrets
from typing import Callable

from genecoder.sdk.plugins import Simulator
from genecoder.formats import SequenceBatch
from genecoder.simulators.batch_utils import (
    RESULT_COVERAGE_KEY,
    clone_batch,
    finalize_batch_statistics,
)


class TemplateChannel(Simulator):  # type: ignore[misc]
    """Skeleton channel plugin showing ``SequenceBatch`` integration."""

    def simulate(self, sequence: str | SequenceBatch) -> SequenceBatch:
        """Return a possibly modified version of ``sequence`` as a batch."""

        batch = self._ensure_batch(sequence)
        mutated = clone_batch(batch)

        coverage_counts: list[int] = []
        dropouts: list[bool] = []
        synthesis_failures: list[bool] = []
        mutation_totals: list[tuple[int, int, int]] = []

        for original, oligo in zip(batch.oligos, mutated.oligos):
            mutated_sequence = self._mutate_read(original.sequence)
            coverage = self._coverage_for(original.sequence, mutated_sequence)

            oligo.sequence = mutated_sequence
            oligo.metadata[RESULT_COVERAGE_KEY] = str(coverage)
            coverage_counts.append(coverage)
            dropouts.append(coverage == 0)
            synthesis_failures.append(False)
            mutation_totals.append((0, 0, 0))

        finalize_batch_statistics(
            mutated,
            coverage_counts,
            dropouts,
            synthesis_failures,
            mutation_totals,
        )

        if mutated.seed is None:
            mutated.seed = secrets.randbits(32)
        mutated.metadata.setdefault("simulator", "template")
        mutated.metadata["sim_seed"] = str(mutated.seed)

        return mutated

    def _ensure_batch(self, sequence: str | SequenceBatch) -> SequenceBatch:
        if isinstance(sequence, SequenceBatch):
            return sequence
        batch_seed = secrets.randbits(32)
        return SequenceBatch.build(
            [("template", sequence)],
            batch_id="template",
            batch_seed=batch_seed,
        )

    def _mutate_read(self, sequence: str) -> str:
        """Return a mutated copy of ``sequence``.

        Override this hook with your channel behaviour.
        """

        return sequence

    def _coverage_for(self, original: str, mutated: str) -> int:
        """Return the coverage depth recorded for ``mutated``.

        Override to report per-oligo coverage counts.
        """

        return 1


def register(register_simulator: Callable[[str, Simulator], None]) -> None:
    """Register the channel simulator with GeneCoder."""

    register_simulator("template", TemplateChannel())
