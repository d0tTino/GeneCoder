from __future__ import annotations

import json
import os
from typing import Iterable, List

from ..channel_config import ChannelConfig
from ..channels.base import BaseChannel
from ..channel_engine import ChannelPipeline as EnginePipeline
from ..formats import SequenceBatch
from ..metrics import metrics
from ..simulation_engine.models import MutationTotals, StageMetrics

__all__ = ["ChannelPipeline"]


class ChannelPipeline(BaseChannel):
    """Compatibility adapter delegating all execution to channel_engine."""

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

    def _build_profile_map(self, config: ChannelConfig) -> dict[str, str]:
        _ = config
        return {}

    def _stage_metrics_from_provenance(
        self, batch: SequenceBatch, _provenance: list[dict[str, object]]
    ) -> list[StageMetrics]:
        totals = MutationTotals(
            substitutions=int(json.loads(batch.metadata.get("sim_mutation_totals", "{}")).get("substitutions", 0))
            if batch.metadata.get("sim_mutation_totals")
            else 0,
            insertions=int(json.loads(batch.metadata.get("sim_mutation_totals", "{}")).get("insertions", 0))
            if batch.metadata.get("sim_mutation_totals")
            else 0,
            deletions=int(json.loads(batch.metadata.get("sim_mutation_totals", "{}")).get("deletions", 0))
            if batch.metadata.get("sim_mutation_totals")
            else 0,
        )
        count = len(batch.oligos)
        stage_names = ["synthesis", "storage_decay", "sequencing"]
        return [
            StageMetrics(stage=stage, oligo_count=count, mutation_totals=totals)
            for stage in stage_names
        ]

    def simulate(self, sequence: str | SequenceBatch, *, config: ChannelConfig | None = None) -> str | SequenceBatch:
        config = config or ChannelConfig()
        is_batch = isinstance(sequence, SequenceBatch)
        batch = sequence if is_batch else SequenceBatch.build([("pipeline", sequence)], batch_id="pipeline")

        resolved = self._resolve_channels(config)
        simulators = [
            (channel.__class__.__name__.lower(), channel)
            for channel in resolved
        ]
        runtime = EnginePipeline.from_simulators(simulators)
        seed_env = os.getenv("GENECODER_SIM_SEED")
        seed = int(seed_env) if seed_env and seed_env.lstrip("-").isdigit() else None
        result_batch, provenance = runtime.run(
            batch,
            profile=self._build_profile_map(config),
            seed=seed,
            config=config,
        )

        self.last_stage_metrics = self._stage_metrics_from_provenance(result_batch, provenance)
        result_batch.metadata["sim_stage_metrics"] = json.dumps(
            [{"stage": metric.stage, "oligo_count": metric.oligo_count} for metric in self.last_stage_metrics]
        )
        metrics.increment("oligos_simulated")
        return result_batch if is_batch else (result_batch.oligos[0].sequence if result_batch.oligos else "")
