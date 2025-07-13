from __future__ import annotations

"""Simple pipeline for processing sequences step by step."""

from typing import Callable, Iterable, Sequence

from .parallel import parallel_map

__all__ = ["SequencePipeline"]


class SequencePipeline:
    """Process sequences through a series of transformation steps."""

    def __init__(self, steps: Iterable[Callable[[str], str]] | None = None) -> None:
        self.steps: list[Callable[[str], str]] = list(steps or [])

    def add_step(self, step: Callable[[str], str]) -> None:
        """Append ``step`` to the pipeline."""
        self.steps.append(step)

    def run(self, sequence: str) -> str:
        """Return ``sequence`` processed by each step."""
        for step in self.steps:
            sequence = step(sequence)
        return sequence

    def run_batch(
        self,
        sequences: Sequence[str],
        *,
        parallel: bool = False,
        workers: int | None = None,
        use_processes: bool = False,
    ) -> list[str]:
        """Apply the pipeline to ``sequences`` optionally in parallel."""
        if parallel:
            return parallel_map(
                self.run,
                sequences,
                workers=workers,
                use_processes=use_processes,
            )
        return [self.run(s) for s in sequences]

