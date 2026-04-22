from __future__ import annotations

import inspect
import json
from collections.abc import Mapping
from typing import Any

from genecoder.channel_engine import ChannelPipeline
from genecoder.formats import SequenceBatch
from genecoder.runtime import make_run_context
from genecoder.runtime.models import SimulateStageInput, SimulateStageOutput
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.simulators.batch_utils import (
    RESULT_COVERAGE_KEY,
    RESULT_DROPOUT_FLAG_KEY,
    RESULT_MUTATION_TOTALS_KEY,
)

from .encode import wrap_single_sequence


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def batch_for_decode(batch: SequenceBatch, *, filter_mutated: bool) -> SequenceBatch:
    filtered = []
    for oligo in batch.oligos:
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

        if dropout_flag:
            continue
        if coverage_int is not None and coverage_int <= 0:
            continue
        if filter_mutated and mutation_flag:
            continue
        filtered.append(oligo)

    if len(filtered) == len(batch.oligos):
        return batch
    return SequenceBatch(
        batch_id=batch.batch_id,
        metadata=dict(batch.metadata),
        seed=batch.seed,
        oligos=list(filtered),
    )


def estimate_coverage(batch: SequenceBatch) -> int | None:
    meta_value = batch.metadata.get("sim_average_coverage")
    if meta_value is not None:
        try:
            return int(round(float(meta_value)))
        except (TypeError, ValueError):
            pass

    coverages: list[int] = []
    for oligo in batch.primary_oligos():
        cov_val = oligo.metadata.get(RESULT_COVERAGE_KEY)
        if cov_val is None:
            continue
        try:
            coverages.append(int(cov_val))
        except (TypeError, ValueError):
            continue
    if coverages:
        return int(round(sum(coverages) / len(coverages)))
    return None


def apply_channel_constructor_parameters(simulator: object, parameters: Mapping[str, Any] | None) -> object:
    if not parameters:
        return simulator
    signature = inspect.signature(type(simulator).__init__)
    accepted = {
        name
        for name, param in signature.parameters.items()
        if name != "self" and param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY)
    }
    kwargs = {key: value for key, value in parameters.items() if key in accepted}
    if not kwargs:
        return simulator
    current_profile = getattr(simulator, "profile", None)
    if "profile" in accepted and "profile" not in kwargs and current_profile is not None:
        kwargs["profile"] = current_profile
    try:
        return type(simulator)(**kwargs)
    except Exception:
        return simulator


class SimulateStageService:
    def run(self, payload: SimulateStageInput) -> SimulateStageOutput:
        runtime_context = payload.run_context or make_run_context()
        is_batch = isinstance(payload.dna, SequenceBatch)
        original_batch = payload.dna if is_batch else wrap_single_sequence(str(payload.dna), batch_id="channel")

        if payload.channel and payload.channel != "none":
            if payload.channel not in SIMULATOR_REGISTRY:
                raise ValueError(f"Unknown channel: {payload.channel}")
            sim = apply_channel_constructor_parameters(SIMULATOR_REGISTRY[payload.channel], payload.channel_parameters)
            pipeline = ChannelPipeline.from_simulators([(payload.channel, sim)])
            mutated_batch, provenance = pipeline.run(original_batch, run_context=runtime_context)

            mutated_batch.metadata["sim_stage_provenance"] = json.dumps(provenance)
            if payload.channel_parameters:
                mutated_batch.metadata["sim_channel_parameters"] = json.dumps(dict(payload.channel_parameters))

            original_sequence = original_batch.combined_sequence()
            mutated_sequence = mutated_batch.combined_sequence()
            from genecoder.core import _count_errors
            subs, ins, dels = _count_errors(original_sequence, mutated_sequence)

            coverage = estimate_coverage(mutated_batch)
            if coverage is None:
                cov_func = getattr(sim, "get_coverage", None)
                if callable(cov_func):
                    try:
                        coverage = int(cov_func(original_sequence))
                    except Exception:
                        coverage = None

            return SimulateStageOutput(
                dna=(mutated_batch if is_batch else mutated_sequence),
                substitutions=subs,
                insertions=ins,
                deletions=dels,
                coverage=coverage,
            )

        return SimulateStageOutput(
            dna=(payload.dna if is_batch else str(payload.dna)),
            substitutions=None,
            insertions=None,
            deletions=None,
            coverage=None,
        )
