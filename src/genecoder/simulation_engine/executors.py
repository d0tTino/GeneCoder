from __future__ import annotations

import json
import random
from typing import Iterable

from ..simulators.batch_utils import load_coverage_distribution, mutation_counts
from ..channel_config import ChannelConfig
from ..formats import SequenceBatch
from .models import (
    DecodeInput,
    EncodedPool,
    MutationTotals,
    ReadRecord,
    ReadSet,
    StageMetrics,
    StoredPool,
    StoredRecord,
    SynthesisOutput,
    SynthesisRecord,
)


class SynthesisExecutor:
    stage_name = "synthesis"

    def execute(self, pool: EncodedPool, *, config: ChannelConfig) -> tuple[SynthesisOutput, StageMetrics]:
        loss = float(config.synthesis_loss or 0.0)
        records: list[SynthesisRecord] = []
        failures = 0
        for oligo in pool.oligos:
            rng = random.Random(oligo.seed)
            failed = rng.random() < loss if loss > 0 else False
            failures += int(failed)
            records.append(SynthesisRecord(oligo=oligo, synthesis_failed=failed))
        return SynthesisOutput(batch_id=pool.batch_id, records=tuple(records)), StageMetrics(
            stage=self.stage_name,
            oligo_count=len(records),
            synthesis_failures=failures,
            details={"configured_synthesis_loss": loss},
        )


class StorageDecayExecutor:
    stage_name = "storage_decay"

    def execute(self, synthesis: SynthesisOutput, *, config: ChannelConfig) -> tuple[StoredPool, StageMetrics]:
        dropout = float(config.dropout_rate or 0.0)
        dist = load_coverage_distribution(config.coverage_distribution)
        records: list[StoredRecord] = []
        dropouts = 0
        coverage_total = 0
        for rec in synthesis.records:
            rng = random.Random(rec.oligo.seed)
            dropped = rec.synthesis_failed or (rng.random() < dropout if dropout > 0 else False)
            coverage = 0
            if not dropped:
                if dist:
                    coverage = int(next(iter(sorted(dist.keys()))))
                else:
                    coverage = 1
            dropouts += int(dropped)
            coverage_total += coverage
            records.append(
                StoredRecord(
                    oligo=rec.oligo,
                    synthesis_failed=rec.synthesis_failed,
                    dropped_out=dropped,
                    planned_coverage=coverage,
                )
            )
        return StoredPool(batch_id=synthesis.batch_id, records=tuple(records)), StageMetrics(
            stage=self.stage_name,
            oligo_count=len(records),
            synthesis_failures=sum(1 for r in records if r.synthesis_failed),
            dropout_total=dropouts,
            total_coverage=coverage_total,
            details={"configured_dropout_rate": dropout},
        )


class SequencingExecutor:
    stage_name = "sequencing"

    def __init__(self, run_channel):
        self._run_channel = run_channel

    def execute(
        self,
        stored: StoredPool,
        *,
        channels: Iterable,
        initial_batch: SequenceBatch,
    ) -> tuple[ReadSet, StageMetrics]:
        batch = initial_batch
        for channel in channels:
            batch = self._run_channel(batch, channel)
        read_records: list[ReadRecord] = []
        sub = ins = dele = 0
        dropouts = 0
        cov_total = 0
        stored_by_id = {r.oligo.oligo_id: r for r in stored.records}
        for oligo in batch.oligos:
            stored_rec = stored_by_id.get(oligo.oligo_id)
            synth_failed = stored_rec.synthesis_failed if stored_rec else False
            dropped = oligo.sequence == ""
            coverage = int(float(oligo.metadata.get("sim_coverage", "0") or 0))
            totals = oligo.metadata.get("sim_mutation_counts")
            parsed = {"substitutions": 0, "insertions": 0, "deletions": 0}
            if totals:
                try:
                    parsed = json.loads(totals)
                except Exception:
                    s, i, d = mutation_counts("", oligo.sequence)
                    parsed = {"substitutions": s, "insertions": i, "deletions": d}
            mt = MutationTotals(
                substitutions=int(parsed.get("substitutions", 0)),
                insertions=int(parsed.get("insertions", 0)),
                deletions=int(parsed.get("deletions", 0)),
            )
            sub += mt.substitutions
            ins += mt.insertions
            dele += mt.deletions
            dropouts += int(dropped)
            cov_total += coverage
            if stored_rec is None:
                continue
            read_records.append(
                ReadRecord(
                    oligo=stored_rec.oligo,
                    consensus=oligo.sequence,
                    coverage=coverage,
                    dropped_out=dropped,
                    synthesis_failed=synth_failed,
                    mutation_totals=mt,
                )
            )
        metrics = StageMetrics(
            stage=self.stage_name,
            oligo_count=len(read_records),
            synthesis_failures=sum(1 for r in read_records if r.synthesis_failed),
            dropout_total=dropouts,
            total_coverage=cov_total,
            mutation_totals=MutationTotals(sub, ins, dele),
        )
        return ReadSet(batch_id=stored.batch_id, reads=tuple(read_records)), metrics


def to_decode_input(reads: ReadSet) -> DecodeInput:
    return DecodeInput(batch_id=reads.batch_id, reads=reads.reads)
