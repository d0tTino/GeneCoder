from __future__ import annotations

import json
import time
from collections.abc import Mapping
from typing import Any

from genecoder.coding.stack import CodingContext, build_layer_metric, compile_stack_from_config, normalize_stack_metrics
from genecoder.formats import SequenceBatch, SequenceOligo
from genecoder.runtime import make_run_context
from genecoder.runtime.models import ConstraintStageInput, DecodeStageInput, DecodeStageOutput
from genecoder.runtime.stages.constraints import ConstraintStageService, resolve_constraint_policy
from genecoder.simulators.batch_utils import (
    RESULT_COVERAGE_KEY,
    RESULT_DROPOUT_FLAG_KEY,
    RESULT_MUTATION_TOTALS_KEY,
)
from genecoder.runtime.stages.simulate import parse_bool

from .encode import wrap_single_sequence


class DecodeStageService:
    def __init__(self, *, constraint_stage: ConstraintStageService | None = None) -> None:
        self._constraint_stage = constraint_stage or ConstraintStageService()

    def run(self, payload: DecodeStageInput) -> DecodeStageOutput:
        runtime_context = payload.run_context or make_run_context()
        policy = payload.constraint_policy or resolve_constraint_policy(payload.fec_info)
        stack = compile_stack_from_config(
            {"codec": payload.codec, "fec": payload.fec},
            constraint_policy=policy,
        )

        batch = payload.dna if isinstance(payload.dna, SequenceBatch) else wrap_single_sequence(str(payload.dna))
        if isinstance(payload.dna, SequenceBatch):
            filtered: list[SequenceOligo] = []
            for oligo in payload.dna.oligos:
                dropout_flag = parse_bool(oligo.metadata.get(RESULT_DROPOUT_FLAG_KEY, False))
                coverage_raw = oligo.metadata.get(RESULT_COVERAGE_KEY)
                try:
                    coverage_int = int(coverage_raw) if coverage_raw is not None else None
                except (TypeError, ValueError):
                    coverage_int = None
                mutation_raw = oligo.metadata.get(RESULT_MUTATION_TOTALS_KEY)
                mutation_flag = False
                if mutation_raw not in (None, ""):
                    mutation_data: Mapping[str, Any] | None
                    if isinstance(mutation_raw, Mapping):
                        mutation_data = mutation_raw
                    elif isinstance(mutation_raw, str):
                        try:
                            parsed = json.loads(mutation_raw)
                        except json.JSONDecodeError:
                            mutation_data = None
                        else:
                            mutation_data = parsed if isinstance(parsed, Mapping) else None
                    else:
                        mutation_data = None
                    if mutation_data is not None:
                        for key in ("substitutions", "insertions", "deletions"):
                            try:
                                if int(mutation_data.get(key, 0)) > 0:
                                    mutation_flag = True
                                    break
                            except (TypeError, ValueError):
                                continue
                if dropout_flag or (coverage_int is not None and coverage_int <= 0) or (
                    payload.filter_mutated and mutation_flag
                ):
                    continue
                filtered.append(oligo)
            if len(filtered) != len(payload.dna.oligos):
                if not filtered:
                    raise ValueError(
                        "No survivor oligos available after filtering; "
                        "adjust channel conditions or disable --filter-mutated."
                    )
                batch = SequenceBatch(
                    batch_id=payload.dna.batch_id,
                    metadata=dict(payload.dna.metadata),
                    seed=payload.dna.seed,
                    oligos=list(filtered),
                )
        survivor_batch = payload.survivor_batch
        if survivor_batch is None and isinstance(payload.dna, SequenceBatch):
            survivor_batch = batch
        if isinstance(batch, SequenceBatch) and not batch.oligos:
            raise ValueError(
                "No survivor oligos available after filtering; "
                "adjust channel conditions or disable --filter-mutated."
            )

        constraint_outcomes: dict[str, Any] = {}
        if policy is not None:
            stage_outcome = self._constraint_stage.run(
                ConstraintStageInput(batch=batch, policy=policy, stage="pre_decode")
            ).payload
            constraint_outcomes = {
                "by_oligo": stage_outcome.get("by_oligo", {}),
                "stages": [{k: v for k, v in stage_outcome.items() if k != "by_oligo"}],
            }

        context_meta: dict[str, Any] = {"batch_id": batch.batch_id, **batch.metadata}
        if payload.fec_info:
            context_meta.update(dict(payload.fec_info))
        if survivor_batch is not None:
            context_meta["survivor_batch"] = survivor_batch
        context = CodingContext(
            block_id="decode-0",
            metadata={**context_meta, "run_context": runtime_context},
            constraint_policy=policy,
        )

        current: bytes | str | SequenceBatch = batch
        decode_metrics: list[dict[str, Any]] = []
        codec_decoded = False
        for layer in reversed(stack):
            before_size = (
                len(current)
                if isinstance(current, (bytes, bytearray, str))
                else len(current.combined_sequence())
            )
            if not codec_decoded and layer.name == payload.codec:
                layer_input: bytes | str | SequenceBatch = current
                if isinstance(layer_input, bytes):
                    layer_input = layer_input.decode("utf-8")
                started_at = time.perf_counter()
                layer_out = layer.decode_block(layer_input, context)
                codec_decoded = True
            else:
                if isinstance(current, str):
                    current = current.encode("utf-8")
                started_at = time.perf_counter()
                layer_out = layer.decode_block(current, context)
            current = layer_out.payload
            after_size = (
                len(current)
                if isinstance(current, (bytes, bytearray, str))
                else len(current.combined_sequence())
            )
            decode_metrics.append(
                build_layer_metric(
                    layer_name=layer.name,
                    layer_type="codec" if layer.name == payload.codec else "fec",
                    stage="decode",
                    before_size=before_size,
                    after_size=after_size,
                    started_at=started_at,
                    corrections=int(layer_out.metadata.get("corrections", 0) or 0),
                )
            )

        if not isinstance(current, (bytes, bytearray)):
            raise TypeError("Decoded payload must be bytes")
        if isinstance(payload.fec_info, dict):
            payload.fec_info["coding_stack"] = normalize_stack_metrics(decode_metrics)
            if constraint_outcomes:
                payload.fec_info["constraint_outcomes"] = dict(constraint_outcomes)

        return DecodeStageOutput(decoded=bytes(current))
