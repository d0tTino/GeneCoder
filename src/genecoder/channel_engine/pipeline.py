from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Mapping

from ..channel_config import ChannelConfig
from ..formats import SequenceBatch
from ..random_utils import reset_rng
from .interfaces import SequencingStage, Stage, StorageStage, SynthesisStage
from .plugins import (
    DecayStorageStage,
    IlluminaSequencingStage,
    NanoporeSequencingStage,
    SimulatorStagePlugin,
    infer_stage_name,
    mutation_totals_from_batch,
)


@dataclass
class ChannelPipeline:
    """Orchestrates synthesis/storage/sequencing stage plugins."""

    synthesis_stages: list[SynthesisStage]
    storage_stages: list[StorageStage]
    sequencing_stages: list[SequencingStage]

    @classmethod
    def from_simulators(
        cls,
        simulators: Iterable[tuple[str, object]],
    ) -> "ChannelPipeline":
        synth: list[SynthesisStage] = []
        storage: list[StorageStage] = []
        sequencing: list[SequencingStage] = []

        for name, simulator in simulators:
            stage = infer_stage_name(name, simulator)
            lowered = name.lower()
            if "illumina" in lowered:
                plugin = IlluminaSequencingStage(simulator=simulator)
                sequencing.append(plugin)
                continue
            if any(token in lowered for token in ("nanopore", "dnarsim", "desp")):
                plugin = NanoporeSequencingStage(simulator=simulator)
                sequencing.append(plugin)
                continue
            if "decay" in lowered:
                plugin = DecayStorageStage(simulator=simulator)
                storage.append(plugin)
                continue

            plugin = SimulatorStagePlugin(simulator=simulator, stage_name=stage)
            if stage == "storage":
                storage.append(plugin)
            elif stage == "sequencing":
                sequencing.append(plugin)
            else:
                synth.append(plugin)
        return cls(synthesis_stages=synth, storage_stages=storage, sequencing_stages=sequencing)

    def _all_stages(self) -> list[Stage]:
        return [*self.synthesis_stages, *self.storage_stages, *self.sequencing_stages]

    def run(
        self,
        batch: SequenceBatch,
        profile: Mapping[str, str] | None = None,
        seed: int | None = None,
        config: ChannelConfig | None = None,
    ) -> tuple[SequenceBatch, list[dict[str, object]]]:
        if seed is not None:
            os.environ["GENECODER_SIM_SEED"] = str(seed)
            reset_rng()

        current = batch
        provenance: list[dict[str, object]] = []
        profiles = dict(profile or {})

        for stage in self._all_stages():
            stage_profile = profiles.get(stage.stage_name)
            result = stage.run(current, profile=stage_profile)
            current = result.batch
            provenance.append(
                {
                    "stage_name": stage.stage_name,
                    "profile_version": result.profile_version,
                    "seed": seed,
                    "mutation_totals": mutation_totals_from_batch(current),
                }
            )

        return current, provenance
