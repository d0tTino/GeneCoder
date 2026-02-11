from __future__ import annotations

import json
from dataclasses import dataclass

from ..formats import SequenceBatch
from ..simulators.base import BaseChannel
from ..simulators.batch_utils import apply_legacy_simulator
from .interfaces import StageResult


@dataclass
class SimulatorStagePlugin:
    """Adapter that exposes an existing simulator as a channel stage plugin."""

    simulator: BaseChannel
    stage_name: str

    def run(self, batch: SequenceBatch, *, profile: str | None = None) -> StageResult:
        sim = self.simulator
        if profile and hasattr(sim, "with_profile"):
            try:
                updated = sim.with_profile(profile)  # type: ignore[attr-defined]
                if isinstance(updated, BaseChannel):
                    sim = updated
            except Exception:
                pass

        if getattr(sim, "supports_batches", False):
            result = sim.simulate(batch)
        else:
            result = apply_legacy_simulator(batch, sim.simulate)  # type: ignore[arg-type]

        if isinstance(result, SequenceBatch):
            out = result
        else:
            out = SequenceBatch.build([(batch.batch_id, str(result))], batch_id=batch.batch_id)

        return StageResult(batch=out, profile_version=profile)


def mutation_totals_from_batch(batch: SequenceBatch) -> dict[str, int]:
    raw = batch.metadata.get("sim_mutation_totals")
    if not raw:
        return {"substitutions": 0, "insertions": 0, "deletions": 0}
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    return {
        "substitutions": int(parsed.get("substitutions", 0) or 0),
        "insertions": int(parsed.get("insertions", 0) or 0),
        "deletions": int(parsed.get("deletions", 0) or 0),
    }


def infer_stage_name(sim_name: str, simulator: object) -> str:
    lowered = sim_name.lower()
    cls_name = simulator.__class__.__name__.lower()
    if "decay" in lowered or "degradation" in cls_name:
        return "storage"
    if any(token in lowered for token in ("illumina", "nanopore", "dnarsim", "desp")):
        return "sequencing"
    return "synthesis"


class IlluminaSequencingStage(SimulatorStagePlugin):
    """Stage plugin wrapping Illumina simulators."""

    def __init__(self, simulator: BaseChannel) -> None:
        super().__init__(simulator=simulator, stage_name="sequencing")


class NanoporeSequencingStage(SimulatorStagePlugin):
    """Stage plugin wrapping Nanopore simulators."""

    def __init__(self, simulator: BaseChannel) -> None:
        super().__init__(simulator=simulator, stage_name="sequencing")


class DecayStorageStage(SimulatorStagePlugin):
    """Stage plugin wrapping decay/storage simulators."""

    def __init__(self, simulator: BaseChannel) -> None:
        super().__init__(simulator=simulator, stage_name="storage")
