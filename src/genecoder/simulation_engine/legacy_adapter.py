from __future__ import annotations

import json

from ..formats import SequenceBatch, SequenceOligo
from .models import DecodeInput, EncodedOligo, EncodedPool, StageMetrics


def to_encoded_pool(batch: SequenceBatch) -> EncodedPool:
    return EncodedPool(
        batch_id=batch.batch_id,
        seed=batch.seed,
        legacy=batch.legacy,
        oligos=tuple(
            EncodedOligo(
                oligo_id=oligo.oligo_id,
                header=oligo.header,
                index=oligo.index,
                sequence=oligo.sequence,
                seed=oligo.seed,
            )
            for oligo in batch.oligos
        ),
    )


def to_sequence_batch(
    decode_input: DecodeInput,
    *,
    template: SequenceBatch,
    stage_metrics: list[StageMetrics],
) -> SequenceBatch:
    out = SequenceBatch(
        batch_id=template.batch_id,
        metadata=dict(template.metadata),
        seed=template.seed,
        legacy=template.legacy,
        oligos=[],
    )
    template_by_id = {oligo.oligo_id: oligo for oligo in template.oligos}
    for read in decode_input.reads:
        src = template_by_id.get(read.oligo.oligo_id)
        metadata = dict(src.metadata if src is not None else {})
        metadata["sim_coverage"] = str(read.coverage)
        metadata["sim_dropout"] = "true" if read.dropped_out else "false"
        metadata["sim_synthesis_failed"] = "true" if read.synthesis_failed else "false"
        metadata["sim_mutation_counts"] = json.dumps(
            {
                "substitutions": read.mutation_totals.substitutions,
                "insertions": read.mutation_totals.insertions,
                "deletions": read.mutation_totals.deletions,
            }
        )
        out.add_oligo(
            SequenceOligo(
                sequence=read.consensus,
                header=read.oligo.header,
                index=read.oligo.index,
                oligo_id=read.oligo.oligo_id,
                metadata=metadata,
                seed=read.oligo.seed,
            )
        )
    out.metadata["sim_stage_metrics"] = json.dumps(
        [
            {
                "stage": sm.stage,
                "oligo_count": sm.oligo_count,
                "synthesis_failures": sm.synthesis_failures,
                "dropout_total": sm.dropout_total,
                "total_coverage": sm.total_coverage,
                "mutation_totals": {
                    "substitutions": sm.mutation_totals.substitutions,
                    "insertions": sm.mutation_totals.insertions,
                    "deletions": sm.mutation_totals.deletions,
                },
                "details": dict(sm.details),
            }
            for sm in stage_metrics
        ]
    )
    return out
