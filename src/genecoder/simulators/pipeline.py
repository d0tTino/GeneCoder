from __future__ import annotations

from typing import Iterable, List
import concurrent.futures
import os


def _run_channel(sequence: str, channel: BaseChannel) -> str:
    return channel.simulate(sequence)

from ..channels.base import BaseChannel
from ..metrics import metrics
from ..channel_config import ChannelConfig

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
        config: ChannelConfig | None = None,
    ) -> str:
        """Return ``sequence`` processed by each channel."""

        if config is None:
            config = ChannelConfig()

        parallel = config.parallel or config.use_mpi
        workers = config.workers
        use_process_pool = config.use_process_pool
        use_mpi = config.use_mpi

        channels = []
        for ch in self.channels:
            if (
                config.illumina_profile is not None
                and hasattr(ch, "profile")
                and ch.__class__.__name__ == "InsilicoSeqChannel"
            ):
                ch = type(ch)(read_length=getattr(ch, "read_length", 150), profile=config.illumina_profile)
            elif (
                config.nanopore_profile is not None
                and hasattr(ch, "profile")
                and ch.__class__.__name__ == "DNArSimChannel"
            ):
                ch = type(ch)(error_rate=getattr(ch, "error_rate", 0.05), profile=config.nanopore_profile)
            channels.append(ch)

        if use_mpi:
            parallel = True

        if not parallel or len(channels) <= 1:
            for channel in channels:
                sequence = channel.simulate(sequence)
            metrics.increment("oligos_simulated")
            return sequence

        if workers is None:
            workers = min(len(channels), os.cpu_count() or 1)

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

        with executor_cls(max_workers=workers) as executor:
            fut: concurrent.futures.Future[str] | None = None
            for channel in channels:
                if fut is None:
                    fut = executor.submit(_run_channel, sequence, channel)
                else:
                    fut = executor.submit(
                        lambda f=fut, ch=channel: _run_channel(f.result(), ch)
                    )

            if fut is not None:
                sequence = fut.result()

        metrics.increment("oligos_simulated")
        return sequence
