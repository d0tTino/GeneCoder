from __future__ import annotations

from typing import Iterable, List
import concurrent.futures
import os

from ..channels.base import BaseChannel
from ..metrics import metrics

__all__ = ["ChannelPipeline"]


class ChannelPipeline(BaseChannel):
    """Apply a sequence of channels to a DNA sequence."""

    def __init__(self, channels: Iterable[BaseChannel] | None = None) -> None:
        self.channels: List[BaseChannel] = list(channels or [])

    def add_channel(self, channel: BaseChannel) -> None:
        """Append ``channel`` to the pipeline."""
        self.channels.append(channel)

    def simulate(
        self,
        sequence: str,
        *,
        parallel: bool = False,
        workers: int | None = None,
        use_process_pool: bool = False,
        use_mpi: bool = False,
    ) -> str:
        """Return ``sequence`` processed by each channel."""

        if use_mpi:
            parallel = True

        if not parallel or len(self.channels) <= 1:
            for channel in self.channels:
                sequence = channel.simulate(sequence)
            metrics.increment("oligos_simulated")
            return sequence

        if workers is None:
            workers = min(len(self.channels), os.cpu_count() or 1)

        if use_mpi:
            try:
                from mpi4py.futures import MPIPoolExecutor
            except Exception as exc:  # pragma: no cover - optional dependency
                raise RuntimeError("mpi4py is required for MPI execution") from exc
            executor_cls = MPIPoolExecutor
        else:
            executor_cls = (
                concurrent.futures.ProcessPoolExecutor
                if use_process_pool
                else concurrent.futures.ThreadPoolExecutor
            )

        current = sequence
        with executor_cls(max_workers=workers) as executor:
            for channel in self.channels:
                current = executor.submit(channel.simulate, current).result()
        metrics.increment("oligos_simulated")
        return current
