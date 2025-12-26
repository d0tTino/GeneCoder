from __future__ import annotations

import concurrent.futures
import json
import os
from typing import Iterable, List


def _run_channel(batch: "SequenceBatch" | str, channel: BaseChannel) -> "SequenceBatch" | str:
    input_is_str = isinstance(batch, str)
    current = batch if isinstance(batch, SequenceBatch) else _batch_from_string(batch)
    if getattr(channel, "supports_batches", False):
        result = channel.simulate(current)
    else:
        result = apply_legacy_simulator(current, channel.simulate)
    if isinstance(result, SequenceBatch):
        if input_is_str:
            return result.oligos[0].sequence if result.oligos else ""
        return result
    return result if input_is_str else _batch_from_string(result)

from ..channels.base import BaseChannel
from ..metrics import metrics
from ..channel_config import ChannelConfig
from ..formats import SequenceBatch
from .batch_utils import (
    CONFIG_COVERAGE_KEY,
    CONFIG_DROPOUT_KEY,
    CONFIG_SYNTHESIS_KEY,
    RESULT_COVERAGE_KEY,
    RESULT_DROPOUT_FLAG_KEY,
    RESULT_MUTATION_LOG_KEY,
    RESULT_MUTATION_TOTALS_KEY,
    RESULT_SYNTHESIS_FLAG_KEY,
    apply_legacy_simulator,
    bool_to_str,
    clone_batch,
    finalize_batch_statistics,
)

__all__ = ["ChannelPipeline"]


def _batch_from_string(sequence: str) -> SequenceBatch:
    batch = SequenceBatch.build([("pipeline", sequence)], batch_id="pipeline")
    if batch.oligos:
        oligo = batch.oligos[0]
        oligo.metadata[RESULT_COVERAGE_KEY] = "1"
        oligo.metadata[RESULT_DROPOUT_FLAG_KEY] = bool_to_str(False)
        oligo.metadata[RESULT_SYNTHESIS_FLAG_KEY] = bool_to_str(False)
        oligo.metadata[RESULT_MUTATION_LOG_KEY] = json.dumps([])
        oligo.metadata[RESULT_MUTATION_TOTALS_KEY] = json.dumps(
            {"substitutions": 0, "insertions": 0, "deletions": 0}
        )
        finalize_batch_statistics(batch, [1], [False], [False], [(0, 0, 0)])
    return batch


def _prepare_batch(
    batch: SequenceBatch, config: ChannelConfig | None
) -> SequenceBatch:
    if config is None:
        return batch
    prepared = clone_batch(batch)
    if config.dropout_rate is not None:
        prepared.metadata[CONFIG_DROPOUT_KEY] = str(float(config.dropout_rate))
    if config.synthesis_loss is not None:
        prepared.metadata[CONFIG_SYNTHESIS_KEY] = str(float(config.synthesis_loss))
    if config.coverage_distribution:
        prepared.metadata[CONFIG_COVERAGE_KEY] = json.dumps(
            {int(k): float(v) for k, v in config.coverage_distribution.items()}
        )
    return prepared


class ChannelPipeline(BaseChannel):
    """Apply a sequence of channels to a DNA sequence."""

    supports_batches = True

    def __init__(self, channels: Iterable[BaseChannel] | None = None) -> None:
        self.channels: List[BaseChannel] = list(channels or [])

    def add_channel(self, channel: BaseChannel) -> None:
        """Append ``channel`` to the pipeline."""
        self.channels.append(channel)

    def simulate(
        self,
        sequence: str | SequenceBatch,
        *,
        config: ChannelConfig | None = None,
    ) -> str | SequenceBatch:
        """Return ``sequence`` processed by each channel."""

        if config is None:
            config = ChannelConfig()

        is_batch = isinstance(sequence, SequenceBatch)
        batch = sequence if is_batch else _batch_from_string(sequence)
        batch = _prepare_batch(batch, config)

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
                if getattr(channel, "supports_batches", False):
                    result = channel.simulate(batch)
                else:
                    result = apply_legacy_simulator(batch, channel.simulate)
                batch = result if isinstance(result, SequenceBatch) else _batch_from_string(result)
            metrics.increment("oligos_simulated")
            return batch if is_batch else (batch.oligos[0].sequence if batch.oligos else "")

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
            done_future: concurrent.futures.Future[SequenceBatch] = concurrent.futures.Future()

            def _dispatch(idx: int, current: SequenceBatch) -> None:
                fut = executor.submit(_run_channel, current, channels[idx])
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

            _dispatch(0, batch)
            batch = done_future.result()

        metrics.increment("oligos_simulated")
        return batch if is_batch else (batch.oligos[0].sequence if batch.oligos else "")
