from __future__ import annotations

import concurrent.futures
import json
import os
from typing import Iterable, List

from ..channel_config import ChannelConfig
from ..channels.base import BaseChannel
from ..formats import SequenceBatch
from ..metrics import metrics
from ..simulation_engine.executors import (
    SequencingExecutor,
    StorageDecayExecutor,
    SynthesisExecutor,
    to_decode_input,
)
from ..simulation_engine.legacy_adapter import to_encoded_pool, to_sequence_batch
from ..simulation_engine.models import StageMetrics
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


def _run_channel(sequence: "SequenceBatch | str", channel: BaseChannel) -> "SequenceBatch | str":
    if isinstance(sequence, SequenceBatch):
        if not getattr(channel, "supports_batches", False):
            return apply_legacy_simulator(sequence, channel.simulate)
        result = channel.simulate(sequence)
        if isinstance(result, SequenceBatch):
            return result
        return _batch_from_string(result)

    if getattr(channel, "supports_batches", False):
        result = channel.simulate(_batch_from_string(sequence))
        if isinstance(result, SequenceBatch):
            return result.oligos[0].sequence if result.oligos else ""
        return result

    return channel.simulate(sequence)


def _batch_from_string(sequence: str) -> SequenceBatch:
    batch = SequenceBatch.build([("pipeline", sequence)], batch_id="pipeline")
    if batch.oligos:
        oligo = batch.oligos[0]
        oligo.metadata[RESULT_COVERAGE_KEY] = "1"
        oligo.metadata[RESULT_DROPOUT_FLAG_KEY] = bool_to_str(False)
        oligo.metadata[RESULT_SYNTHESIS_FLAG_KEY] = bool_to_str(False)
        oligo.metadata[RESULT_MUTATION_LOG_KEY] = json.dumps([])
        oligo.metadata[RESULT_MUTATION_TOTALS_KEY] = json.dumps({"substitutions": 0, "insertions": 0, "deletions": 0})
        finalize_batch_statistics(batch, [1], [False], [False], [(0, 0, 0)])
    return batch


def _prepare_batch(batch: SequenceBatch, config: ChannelConfig | None) -> SequenceBatch:
    if config is None:
        return batch
    prepared = clone_batch(batch)
    if config.dropout_rate is not None:
        prepared.metadata[CONFIG_DROPOUT_KEY] = str(float(config.dropout_rate))
    if config.synthesis_loss is not None:
        prepared.metadata[CONFIG_SYNTHESIS_KEY] = str(float(config.synthesis_loss))
    if config.coverage_distribution:
        prepared.metadata[CONFIG_COVERAGE_KEY] = json.dumps({int(k): float(v) for k, v in config.coverage_distribution.items()})
    return prepared


def _run_channels(
    batch: SequenceBatch,
    channels: list[BaseChannel],
    *,
    config: ChannelConfig,
) -> SequenceBatch:
    parallel = config.parallel or config.use_mpi
    if config.use_mpi:
        parallel = True
    if not parallel or len(channels) <= 1:
        current = batch
        for channel in channels:
            current = _run_channel(current, channel)
        return current

    workers = config.workers or min(len(channels), os.cpu_count() or 1)
    if config.use_mpi:
        try:
            from mpi4py.futures import MPIPoolExecutor
        except Exception as exc:
            raise RuntimeError("mpi4py is required for MPI execution") from exc
        executor_cls = MPIPoolExecutor
    else:
        executor_cls = concurrent.futures.ProcessPoolExecutor if config.use_process_pool else concurrent.futures.ThreadPoolExecutor

    with executor_cls(max_workers=workers) as executor:
        current: SequenceBatch = batch
        for channel in channels:
            current = executor.submit(_run_channel, current, channel).result()
    return current


class ChannelPipeline(BaseChannel):
    """Apply staged sequencing simulation to a DNA sequence or batch."""

    supports_batches = True

    def __init__(self, channels: Iterable[BaseChannel] | None = None) -> None:
        self.channels: List[BaseChannel] = list(channels or [])
        self.last_stage_metrics: list[StageMetrics] = []

    def add_channel(self, channel: BaseChannel) -> None:
        self.channels.append(channel)

    def _resolve_channels(self, config: ChannelConfig) -> list[BaseChannel]:
        from ..dnarsim_adapter import DNArSimChannel
        from ..insilicoseq_adapter import InSilicoSeqChannel
        from ..simulators.illumina import IlluminaChannel
        from ..simulators.nanopore import NanoporeChannel

        resolved: list[BaseChannel] = []
        for channel in self.channels:
            ch = channel
            if config.illumina_profile is not None and isinstance(ch, (InSilicoSeqChannel, IlluminaChannel)):
                ch = ch.with_profile(config.illumina_profile)
            elif config.nanopore_profile is not None and isinstance(ch, (DNArSimChannel, NanoporeChannel)):
                ch = ch.with_profile(config.nanopore_profile)
            resolved.append(ch)
        return resolved

    def simulate(self, sequence: str | SequenceBatch, *, config: ChannelConfig | None = None) -> str | SequenceBatch:
        config = config or ChannelConfig()
        is_batch = isinstance(sequence, SequenceBatch)
        batch = sequence if is_batch else _batch_from_string(sequence)
        batch = _prepare_batch(batch, config)

        encoded_pool = to_encoded_pool(batch)
        synthesis_out, synthesis_metrics = SynthesisExecutor().execute(encoded_pool, config=config)
        stored_pool, storage_metrics = StorageDecayExecutor().execute(synthesis_out, config=config)
        channels = self._resolve_channels(config)

        sequencing_executor = SequencingExecutor(
            _run_channel
        )
        read_set, sequencing_metrics = sequencing_executor.execute(
            stored_pool,
            channels=[],
            initial_batch=_run_channels(batch, channels, config=config),
        )

        self.last_stage_metrics = [synthesis_metrics, storage_metrics, sequencing_metrics]
        result_batch = to_sequence_batch(
            to_decode_input(read_set),
            template=batch,
            stage_metrics=self.last_stage_metrics,
        )
        metrics.increment("oligos_simulated")
        return result_batch if is_batch else (result_batch.oligos[0].sequence if result_batch.oligos else "")
