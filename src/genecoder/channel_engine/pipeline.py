from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Iterable, Mapping

from ..channel_config import ChannelConfig
from ..formats import SequenceBatch
from ..runtime import RunContext, make_run_context
from .interfaces import (
    SequencingStage,
    SimulatorStage,
    StageContext,
    StageMutationTotals,
    StageProvenance,
    StorageStage,
    SynthesisStage,
)
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

    def _all_stages(self) -> list[SimulatorStage]:
        return [*self.synthesis_stages, *self.storage_stages, *self.sequencing_stages]

    def run(
        self,
        batch: SequenceBatch,
        profile: Mapping[str, str] | None = None,
        seed: int | None = None,
        run_context: RunContext | None = None,
        config: ChannelConfig | None = None,
    ) -> tuple[SequenceBatch, list[dict[str, object]]]:
        runtime_context = run_context or make_run_context(global_seed=seed)
        stage_seed = runtime_context.simulate_seed
        rng = random.Random(stage_seed) if stage_seed is not None else random.Random()
        context = StageContext(
            run_context=runtime_context,
            seed=stage_seed,
            rng=rng,
            metadata=dict(batch.metadata),
        )

        current = batch
        provenance: list[StageProvenance] = []
        profiles = dict(profile or {})

        for stage in self._all_stages():
            stage_profile = profiles.get(stage.stage_name)
            result = stage.run(current, profile=stage_profile, context=context)
            current = result.output_batch
            provenance.append(
                StageProvenance(
                    stage_name=stage.stage_name,
                    stage_kind=stage.stage_name,
                    profile=stage_profile,
                    profile_version=result.profile_version,
                    seed=stage_seed,
                    mutation_totals=StageMutationTotals(**mutation_totals_from_batch(current)),
                    metadata=dict(result.metadata),
                )
            )

        return current, [entry.to_dict() for entry in provenance]
