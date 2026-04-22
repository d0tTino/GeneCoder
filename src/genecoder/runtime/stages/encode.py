from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from genecoder.coding.stack import CodingContext, build_layer_metric, compile_stack_from_config, normalize_stack_metrics
from genecoder.formats import SequenceBatch
from genecoder.runtime import make_run_context
from genecoder.runtime.models import ConstraintStageInput, EncodeStageInput, EncodeStageOutput
from genecoder.runtime.stages.constraints import ConstraintStageService


def wrap_single_sequence(
    sequence: str,
    *,
    batch_id: str = "sequence",
    codec: str | None = None,
) -> SequenceBatch:
    tokens = [f"batch_id={batch_id}", "oligo_index=1"]
    if codec:
        tokens.append(f"codec={codec}")
    header = " ".join(tokens)
    batch = SequenceBatch.build([(header, sequence)], batch_id=batch_id)
    if codec:
        batch.metadata.setdefault("codec", codec)
    return batch


class EncodeStageService:
    def __init__(self, *, constraint_stage: ConstraintStageService | None = None) -> None:
        self._constraint_stage = constraint_stage or ConstraintStageService()

    def run(self, payload: EncodeStageInput) -> EncodeStageOutput:
        stack = compile_stack_from_config(
            {"codec": payload.codec, "fec": payload.fec},
            constraint_policy=payload.constraint_policy,
        )
        runtime_context = payload.run_context or make_run_context()
        context = CodingContext(
            block_id="encode-0",
            constraint_policy=payload.constraint_policy,
            metadata={"run_context": runtime_context},
        )
        current: bytes | str | SequenceBatch = payload.data
        layer_info: dict[str, Mapping[str, Any]] = {}
        layer_metrics: list[dict[str, Any]] = []
        for layer in stack:
            before_size = (
                len(current)
                if isinstance(current, (bytes, bytearray, str))
                else len(current.combined_sequence())
            )
            started_at = time.perf_counter()
            layer_out = layer.encode_block(current, context)
            current = layer_out.payload
            info_value = layer_out.metadata.get("fec_info")
            if isinstance(info_value, Mapping):
                layer_info[layer.name] = dict(info_value)
            after_size = (
                len(current)
                if isinstance(current, (bytes, bytearray, str))
                else len(current.combined_sequence())
            )
            layer_metrics.append(
                build_layer_metric(
                    layer_name=layer.name,
                    layer_type="codec" if layer.name == payload.codec else "fec",
                    stage="encode",
                    before_size=before_size,
                    after_size=after_size,
                    started_at=started_at,
                )
            )

        encoded = current
        if isinstance(encoded, SequenceBatch):
            batch = encoded
        elif isinstance(encoded, str):
            batch = wrap_single_sequence(encoded, batch_id=f"{payload.codec}-batch", codec=payload.codec)
        else:
            raise TypeError("Codec implementations must return a string or SequenceBatch")

        constraint_outcomes: list[dict[str, Any]] = []
        stage_outcome: dict[str, Any] = {}
        if payload.constraint_policy is not None:
            stage_outcome = self._constraint_stage.run(
                ConstraintStageInput(
                    batch=batch,
                    policy=payload.constraint_policy,
                    stage="encode",
                )
            ).payload
            constraint_outcomes.append({k: v for k, v in stage_outcome.items() if k != "by_oligo"})

        normalized_stack = normalize_stack_metrics(layer_metrics, "".join(ol.sequence for ol in batch.oligos))
        batch.metadata.setdefault("coding_stack", normalized_stack)

        if payload.constraint_policy is not None:
            batch.metadata["constraint_policy"] = payload.constraint_policy.to_dict()
            existing = batch.metadata.get("constraint_outcomes")
            merged = dict(existing) if isinstance(existing, Mapping) else {}
            merged["by_oligo"] = stage_outcome.get("by_oligo", {})
            merged["stages"] = constraint_outcomes
            batch.metadata["constraint_outcomes"] = merged

        fec_info: Mapping[str, Any] | None = None
        if layer_info:
            info_dict: dict[str, Any] = {
                "layer_info": layer_info,
                "coding_stack": normalized_stack,
            }
            if payload.fec and payload.fec in layer_info:
                info_dict.update(dict(layer_info[payload.fec]))
            if payload.constraint_policy is not None:
                info_dict["constraint_policy"] = payload.constraint_policy.to_dict()
                info_dict["constraint_outcomes"] = dict(batch.metadata.get("constraint_outcomes", {}))
            info_dict.setdefault("batch_id", batch.batch_id)
            info_dict.setdefault("batch_metadata", dict(batch.metadata))
            fec_info = info_dict

        return EncodeStageOutput(encoded_batch=batch, fec_info=fec_info)
