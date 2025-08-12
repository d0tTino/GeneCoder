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

        from ..dnarsim_adapter import DNArSimChannel
        from ..insilicoseq_adapter import InSilicoSeqChannel
        from ..simulators.illumina import IlluminaChannel
        from ..simulators.nanopore import NanoporeChannel

        channels = []
        for ch in self.channels:
            if (
                config.illumina_profile is not None
                and isinstance(ch, (InSilicoSeqChannel, IlluminaChannel))
            ):
                ch = ch.with_profile(config.illumina_profile)
            elif (
                config.nanopore_profile is not None
                and isinstance(ch, (DNArSimChannel, NanoporeChannel))
            ):
                ch = ch.with_profile(config.nanopore_profile)
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
            done_future: concurrent.futures.Future[str] = concurrent.futures.Future()

            def _dispatch(idx: int, seq: str) -> None:
                fut = executor.submit(_run_channel, seq, channels[idx])
                if hasattr(fut, "add_done_callback"):
                    if idx + 1 < len(channels):
                        fut.add_done_callback(
                            lambda f, i=idx + 1: _dispatch(i, f.result())
                        )
                    else:
                        fut.add_done_callback(lambda f: done_future.set_result(f.result()))
                else:
                    res = fut.result()
                    if idx + 1 < len(channels):
                        _dispatch(idx + 1, res)
                    else:
                        done_future.set_result(res)

            _dispatch(0, sequence)
            sequence = done_future.result()

        metrics.increment("oligos_simulated")
        return sequence
