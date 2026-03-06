from __future__ import annotations

"""Legacy string-oriented sequence pipeline kept in application layer."""

import warnings
from typing import Callable, Iterable, Sequence

from genecoder.parallel import parallel_map


class SequencePipeline:
    """Legacy string-based pipeline wrapper."""

    def __init__(self, steps: Iterable[Callable[[str], str]] | None = None) -> None:
        warnings.warn(
            "SequencePipeline is deprecated; use genecoder.app.RunPipelineUseCase instead",
            DeprecationWarning,
            stacklevel=2,
        )
        self.steps: list[Callable[[str], str]] = list(steps or [])

    def add_step(self, step: Callable[[str], str]) -> None:
        self.steps.append(step)

    def run(self, sequence: str) -> str:
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
        if parallel:
            return parallel_map(
                self.run,
                sequences,
                workers=workers,
                use_processes=use_processes,
            )
        return [self.run(s) for s in sequences]
