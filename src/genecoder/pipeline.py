from __future__ import annotations

"""Simple pipeline for processing sequences step by step."""

from pathlib import Path
import warnings
from typing import Any, Callable, Iterable, Mapping, Sequence, Tuple

from .plugin_manager import init_plugins
from .parallel import parallel_map
from .formats import SequenceBatch
from . import core

__all__ = ["SequencePipeline", "run_pipeline"]


class SequencePipeline:
    """Legacy string-based pipeline wrapper.

    This adapter exists for backwards compatibility with older integrations
    that expected ``SequencePipeline`` to operate on plain strings. New code
    should prefer the SequenceBatch-aware helpers in :mod:`genecoder.core`.
    """

    def __init__(self, steps: Iterable[Callable[[str], str]] | None = None) -> None:
        warnings.warn(
            "SequencePipeline is deprecated; use genecoder.core helpers instead",
            DeprecationWarning,
            stacklevel=2,
        )
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


def run_pipeline(
    codec: str,
    fec_backend: str | None,
    channel: str | None,
    input_path: str,
    output_path: str,
) -> Tuple[bytes, dict[str, Any], Mapping[str, Any] | None]:
    """Process ``input_path`` through the selected codec, FEC and channel."""

    init_plugins()

    original_data = Path(input_path).read_bytes()
    dna_batch, fec_info = core.encode(codec, fec_backend, original_data)

    selected_channel = channel
    if fec_backend == "fountain" and channel in {"simple", "nanopore"}:
        selected_channel = None

    simulated_batch, subs, ins, dels, coverage = core.simulate(selected_channel, dna_batch)
    if not isinstance(simulated_batch, SequenceBatch):
        simulated_batch = SequenceBatch.build(
            [
                (
                    dna_batch.first_header() or "batch_id=pipeline oligo_index=1",
                    str(simulated_batch),
                )
            ],
            batch_id=dna_batch.batch_id,
        )

    decoded = core.decode(codec, fec_backend, simulated_batch, fec_info)
    Path(output_path).write_bytes(decoded)

    metrics_dict = core.metrics(
        simulated_batch,
        original_data,
        decoded,
        fec_backend,
        subs,
        ins,
        dels,
        coverage,
    )
    return decoded, metrics_dict, fec_info

