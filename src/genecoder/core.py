from __future__ import annotations

"""Simple encode/ECC/channel/decode pipeline utilities."""

import json
import time
from collections import Counter
from pathlib import Path
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Sequence, Tuple

from .gc_constrained_encoder import calculate_gc_content
from .utils import get_max_homopolymer_length

from .plugin_manager import init_plugins
from .runtime import RunContext, make_run_context
from .simulators import SIMULATOR_REGISTRY
from .channel_engine import ChannelPipeline
from .coding.stack import (
    CodingContext,
    build_layer_metric,
    compile_legacy_stack,
    compile_stack_from_config,
    normalize_stack_metrics,
    plan_stack_from_config,
)
from .formats import SequenceBatch, SequenceOligo
from .constraints import ConstraintPolicy, ConstraintRepairPipeline, load_constraint_policy
from .simulators.batch_utils import (
    RESULT_COVERAGE_KEY,
    RESULT_DROPOUT_FLAG_KEY,
    RESULT_MUTATION_TOTALS_KEY,
)

if TYPE_CHECKING:
    from .synthesis import SynthesisConstraints

__all__ = [
    "CanonicalRuntimeResult",
    "encode",
    "simulate",
    "decode",
    "metrics",
    "run_canonical_pipeline",
    "run_pipeline",
    "compile_coding_stack",
    "inspect_coding_plan",
]


@dataclass(slots=True)
class CanonicalRuntimeResult:
    """Canonical encode/simulate/decode execution artifact.

    This dataclass defines the single internal runtime boundary for pipeline
    execution in GeneCoder.
    """

    original_data: bytes
    encoded_batch: SequenceBatch
    simulated_batch: SequenceBatch
    decode_input: SequenceBatch
    survivor_batch: SequenceBatch
    decoded: bytes
    metrics: dict[str, Any]
    fec_info: Mapping[str, Any] | None
    substitutions: int | None
    insertions: int | None
    deletions: int | None
    coverage: int | None



def _levenshtein_counts(original: str, mutated: str) -> tuple[int, int, int]:
    """Return substitution, insertion and deletion counts using Levenshtein ops."""
    try:  # Prefer the optimized python-Levenshtein package if available
        from Levenshtein import editops

        ops = editops(original, mutated)

        def get_tag(op: Any) -> str:  # noqa: D401,ANN401
            return str(op[0])

    except Exception:  # pragma: no cover - fallback to rapidfuzz or difflib
        try:
            from rapidfuzz.distance import Levenshtein as RF

            ops = RF.editops(original, mutated)

            def get_tag(op: Any) -> str:  # noqa: D401,ANN401
                return str(op.tag)

        except Exception:
            import difflib

            def _trim_common_affixes(left: str, right: str) -> tuple[str, str]:
                min_len = min(len(left), len(right))
                start = 0
                while start < min_len and left[start] == right[start]:
                    start += 1
                if start == len(left) and start == len(right):
                    return "", ""
                end = 0
                while end < min_len - start and left[-1 - end] == right[-1 - end]:
                    end += 1
                left_mid = left[start : len(left) - end if end else len(left)]
                right_mid = right[start : len(right) - end if end else len(right)]
                return left_mid, right_mid

            def _difflib_counts(left: str, right: str) -> tuple[int, int, int]:
                left_mid, right_mid = _trim_common_affixes(left, right)
                if not left_mid and not right_mid:
                    return 0, 0, 0
                if not left_mid:
                    return 0, len(right_mid), 0
                if not right_mid:
                    return 0, 0, len(left_mid)
                if len(left_mid) == len(right_mid):
                    subs = sum(1 for a, b in zip(left_mid, right_mid) if a != b)
                    return subs, 0, 0
                subs = ins = dels = 0
                ops = difflib.SequenceMatcher(None, left_mid, right_mid).get_opcodes()
                for tag, i1, i2, j1, j2 in ops:
                    if tag == "replace":
                        overlap = min(i2 - i1, j2 - j1)
                        subs += overlap
                        dels += (i2 - i1) - overlap
                        ins += (j2 - j1) - overlap
                    elif tag == "insert":
                        ins += j2 - j1
                    elif tag == "delete":
                        dels += i2 - i1
                return subs, ins, dels

            return _difflib_counts(original, mutated)

    subs = ins = dels = 0
    for op in ops:
        tag = get_tag(op)
        if tag == "replace":
            subs += 1
        elif tag == "insert":
            ins += 1
        elif tag == "delete":
            dels += 1
    return subs, ins, dels


_count_errors = _levenshtein_counts


def _gc_distribution(sequence: str, window: int = 50) -> List[float]:
    """Return GC content for non-overlapping windows in ``sequence``."""

    values: List[float] = []
    for i in range(0, len(sequence), window):
        chunk = sequence[i : i + window]
        if not chunk:
            break
        gc = sum(1 for base in chunk if base in "GCgc") / len(chunk)
        values.append(gc)
    return values


def _homopolymer_runs(sequence: str) -> List[int]:
    """Return counts of homopolymer runs by length for ``sequence``."""

    if not sequence:
        return []
    counts: Dict[int, int] = {}
    current = sequence[0]
    run = 1
    for base in sequence[1:]:
        if base == current:
            run += 1
        else:
            counts[run] = counts.get(run, 0) + 1
            current = base
            run = 1
    counts[run] = counts.get(run, 0) + 1
    max_run = max(counts)
    return [counts.get(i, 0) for i in range(1, max_run + 1)]


def _wrap_single_sequence(
    sequence: str,
    *,
    batch_id: str = "sequence",
    codec: str | None = None,
) -> SequenceBatch:
    """Return a :class:`SequenceBatch` for a legacy string ``sequence``."""

    tokens = [f"batch_id={batch_id}", "oligo_index=1"]
    if codec:
        tokens.append(f"codec={codec}")
    header = " ".join(tokens)
    batch = SequenceBatch.build([(header, sequence)], batch_id=batch_id)
    if codec:
        batch.metadata.setdefault("codec", codec)
    return batch


def _resolve_constraint_policy(raw: Mapping[str, Any] | None) -> ConstraintPolicy | None:
    if not raw:
        return None
    policy_raw = raw.get("constraint_policy")
    if policy_raw is None:
        return None
    if isinstance(policy_raw, ConstraintPolicy):
        return policy_raw
    if isinstance(policy_raw, Mapping):
        return load_constraint_policy(policy_raw)
    return None


def _constraint_outcome_payload(result: object) -> dict[str, Any]:
    from genecoder.constraints.repair_pipeline import RepairPipelineResult

    if not isinstance(result, RepairPipelineResult):
        return {}
    return {
        "stage": result.stage,
        "violations": {
            "before": result.report_before.count,
            "after": result.report_after.count,
            "pressure_before": result.report_before.pressure,
            "pressure_after": result.report_after.pressure,
        },
        "repairs_applied": len(result.repair.changes) if result.repair is not None else 0,
        "repair_strategy": result.repair.strategy if result.repair is not None else None,
        "residual_risk": result.residual_risk,
    }


def encode(
    codec: str,
    fec: str | None,
    data: bytes,
    *,
    constraint_policy: ConstraintPolicy | None = None,
    run_context: RunContext | None = None,
) -> Tuple[SequenceBatch, Mapping[str, Any] | None]:
    """Return encoded :class:`SequenceBatch` for ``data`` and optional FEC info."""

    stack = compile_legacy_stack(codec, fec, constraint_policy=constraint_policy)
    runtime_context = run_context or make_run_context()
    context = CodingContext(
        block_id="encode-0",
        constraint_policy=constraint_policy,
        metadata={"run_context": runtime_context},
    )
    current: bytes | str | SequenceBatch = data
    layer_info: dict[str, Mapping[str, Any]] = {}
    layer_metrics: list[dict[str, Any]] = []
    for layer in stack:
        before_size = (
            len(current)
            if isinstance(current, (bytes, bytearray, str))
            else len(current.primary_sequence())
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
            else len(current.primary_sequence())
        )
        layer_metrics.append(
            build_layer_metric(
                layer_name=layer.name,
                layer_type="codec" if layer.name == codec else "fec",
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
        batch = _wrap_single_sequence(encoded, batch_id=f"{codec}-batch", codec=codec)
    else:
        raise TypeError(
            "Codec implementations must return a string or SequenceBatch"
        )

    constraint_outcomes: list[dict[str, Any]] = []
    if constraint_policy is not None:
        pipeline = ConstraintRepairPipeline(constraint_policy)
        gate_result = pipeline.run(batch.primary_sequence(), stage="encode")
        constraint_outcomes.append(_constraint_outcome_payload(gate_result))
        if gate_result.sequence != batch.primary_sequence() and batch.oligos:
            batch.oligos[0].sequence = gate_result.sequence

    normalized_stack = normalize_stack_metrics(layer_metrics, batch.primary_sequence())
    batch.metadata.setdefault("coding_stack", normalized_stack)
    if constraint_policy is not None:
        batch.metadata["constraint_policy"] = constraint_policy.to_dict()
        batch.metadata["constraint_outcomes"] = constraint_outcomes

    fec_info: Mapping[str, Any] | None = None
    if layer_info:
        info_dict: dict[str, Any] = {
            "layer_info": layer_info,
            "coding_stack": normalized_stack,
        }
        if fec and fec in layer_info:
            info_dict.update(dict(layer_info[fec]))
        if constraint_policy is not None:
            info_dict["constraint_policy"] = constraint_policy.to_dict()
            info_dict["constraint_outcomes"] = list(constraint_outcomes)
        info_dict.setdefault("batch_id", batch.batch_id)
        info_dict.setdefault("batch_metadata", dict(batch.metadata))
        fec_info = info_dict

    return batch, fec_info


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _batch_for_decode(batch: SequenceBatch, *, filter_mutated: bool) -> SequenceBatch:
    filtered: list[SequenceOligo] = []
    for oligo in batch.oligos:
        dropout_flag = _parse_bool(oligo.metadata.get(RESULT_DROPOUT_FLAG_KEY, False))
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


def run_canonical_pipeline(
    codec: str,
    fec: str | None,
    channel: str | None,
    original_data: bytes,
    *,
    filter_mutated: bool = False,
    run_context: RunContext | None = None,
) -> CanonicalRuntimeResult:
    """Execute the canonical internal runtime route: encode → simulate → decode."""

    init_plugins()
    runtime_context = run_context or make_run_context()

    encoded_batch, fec_info = encode(codec, fec, original_data, run_context=runtime_context)
    try:
        simulated, subs, ins, dels, coverage = simulate(
            channel,
            encoded_batch,
            run_context=runtime_context,
        )
    except TypeError as exc:
        if "run_context" not in str(exc):
            raise
        simulated, subs, ins, dels, coverage = simulate(channel, encoded_batch)
    simulated_batch = (
        simulated if isinstance(simulated, SequenceBatch) else _wrap_single_sequence(str(simulated))
    )
    decode_input = _batch_for_decode(simulated_batch, filter_mutated=filter_mutated)
    decoded = decode(
        codec,
        fec,
        decode_input,
        fec_info,
        filter_mutated=filter_mutated,
        survivor_batch=decode_input,
        run_context=runtime_context,
    )
    metrics_dict = metrics(
        simulated_batch,
        original_data,
        decoded,
        fec,
        subs,
        ins,
        dels,
        coverage,
        stack_metrics=(dict(fec_info).get("coding_stack") if isinstance(fec_info, Mapping) else None),
        constraint_outcomes=(
            dict(fec_info).get("constraint_outcomes") if isinstance(fec_info, Mapping) else None
        ),
    )
    return CanonicalRuntimeResult(
        original_data=original_data,
        encoded_batch=encoded_batch,
        simulated_batch=simulated_batch,
        decode_input=decode_input,
        survivor_batch=decode_input,
        decoded=decoded,
        metrics=metrics_dict,
        fec_info=fec_info,
        substitutions=subs,
        insertions=ins,
        deletions=dels,
        coverage=coverage,
    )


def _estimate_coverage(batch: SequenceBatch) -> int | None:
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


def simulate(
    channel: str | None,
    dna: SequenceBatch | str,
    *,
    run_context: RunContext | None = None,
) -> Tuple[SequenceBatch | str, int | None, int | None, int | None, int | None]:
    """Return ``dna`` possibly mutated by ``channel`` and error counts."""

    runtime_context = run_context or make_run_context()
    is_batch = isinstance(dna, SequenceBatch)
    original_batch = dna if is_batch else _wrap_single_sequence(str(dna), batch_id="channel")

    if channel and channel != "none":
        if channel not in SIMULATOR_REGISTRY:
            raise ValueError(f"Unknown channel: {channel}")
        sim = SIMULATOR_REGISTRY[channel]
        pipeline = ChannelPipeline.from_simulators([(channel, sim)])
        mutated_batch, _ = pipeline.run(
            original_batch,
            run_context=runtime_context,
        )

        original_sequence = original_batch.primary_sequence()
        mutated_sequence = mutated_batch.primary_sequence()
        subs, ins, dels = _count_errors(original_sequence, mutated_sequence)

        coverage = _estimate_coverage(mutated_batch)
        if coverage is None:
            cov_func = getattr(sim, "get_coverage", None)
            if callable(cov_func):
                try:
                    coverage = int(cov_func(original_sequence))
                except Exception:  # pragma: no cover - simulator failed
                    coverage = None

        return (
            mutated_batch if is_batch else mutated_sequence,
            subs,
            ins,
            dels,
            coverage,
        )

    return (dna if is_batch else str(dna)), None, None, None, None


def decode(
    codec: str,
    fec: str | None,
    dna: SequenceBatch | str,
    fec_info: Mapping[str, Any] | None,
    *,
    filter_mutated: bool = True,
    survivor_batch: SequenceBatch | None = None,
    constraint_policy: ConstraintPolicy | None = None,
    run_context: RunContext | None = None,
) -> bytes:
    """Return decoded bytes from ``dna`` applying optional FEC.

    Args:
        filter_mutated: When ``True`` (default), oligos carrying positive
            mutation totals are removed before decoding alongside dropout and
            zero-coverage oligos. Set to ``False`` to retain mutated oligos.
    """

    runtime_context = run_context or make_run_context()
    policy = constraint_policy or _resolve_constraint_policy(fec_info)
    stack = compile_legacy_stack(codec, fec, constraint_policy=policy)

    batch = dna if isinstance(dna, SequenceBatch) else _wrap_single_sequence(str(dna))
    if isinstance(dna, SequenceBatch):
        filtered: list[SequenceOligo] = []
        for oligo in dna.oligos:
            dropout_flag = _parse_bool(oligo.metadata.get(RESULT_DROPOUT_FLAG_KEY, False))
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
                filter_mutated and mutation_flag
            ):
                continue
            filtered.append(oligo)
        if len(filtered) != len(dna.oligos):
            if not filtered:
                raise ValueError(
                    "No survivor oligos available after filtering; "
                    "adjust channel conditions or disable --filter-mutated."
                )
            batch = SequenceBatch(
                batch_id=dna.batch_id,
                metadata=dict(dna.metadata),
                seed=dna.seed,
                oligos=list(filtered),
            )
    if survivor_batch is None and isinstance(dna, SequenceBatch):
        survivor_batch = batch
    if isinstance(batch, SequenceBatch) and not batch.oligos:
        raise ValueError(
            "No survivor oligos available after filtering; "
            "adjust channel conditions or disable --filter-mutated."
        )
    constraint_outcomes: list[dict[str, Any]] = []
    if policy is not None:
        pipeline = ConstraintRepairPipeline(policy)
        gate = pipeline.run(batch.primary_sequence(), stage="pre_decode")
        constraint_outcomes.append(_constraint_outcome_payload(gate))
        if gate.sequence != batch.primary_sequence() and batch.oligos:
            batch.oligos[0].sequence = gate.sequence
    context_meta: dict[str, Any] = {"batch_id": batch.batch_id, **batch.metadata}
    if fec_info:
        context_meta.update(dict(fec_info))
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
            else len(current.primary_sequence())
        )
        if not codec_decoded and layer.name == codec:
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
            else len(current.primary_sequence())
        )
        decode_metrics.append(
            build_layer_metric(
                layer_name=layer.name,
                layer_type="codec" if layer.name == codec else "fec",
                stage="decode",
                before_size=before_size,
                after_size=after_size,
                started_at=started_at,
                corrections=int(layer_out.metadata.get("corrections", 0) or 0),
            )
        )

    if not isinstance(current, (bytes, bytearray)):
        raise TypeError("Decoded payload must be bytes")
    if isinstance(fec_info, dict):
        fec_info["coding_stack"] = normalize_stack_metrics(decode_metrics)
        if constraint_outcomes:
            fec_info["constraint_outcomes"] = constraint_outcomes
    return bytes(current)


def metrics(
    dna: SequenceBatch | str,
    original_data: bytes,
    decoded: bytes,
    fec: str | None,
    subs: int | None = None,
    ins: int | None = None,
    dels: int | None = None,
    coverage: int | None = None,
    constraints: SynthesisConstraints | None = None,
    *,
    oligos: Sequence[str] | None = None,
    dropout_flags: Sequence[bool] | None = None,
    ecc_outcomes: Mapping[str, Sequence[bool | float]] | None = None,
    stack_metrics: Mapping[str, Any] | None = None,
    constraint_outcomes: Sequence[Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Return quality metrics for ``dna`` and decode results."""

    batch = dna if isinstance(dna, SequenceBatch) else None
    if batch is not None:
        base_sequence = batch.primary_sequence() or batch.combined_sequence()
        primary_oligos = batch.primary_oligos() or batch.oligos
        sequences = [ol.sequence for ol in primary_oligos] or [base_sequence]

        per_oligo_dropout: list[bool] = []
        per_oligo_coverage: list[int | None] = []
        per_oligo_mutations: list[dict[str, int]] = []
        for ol in primary_oligos:
            dropout_flag = _parse_bool(ol.metadata.get(RESULT_DROPOUT_FLAG_KEY, False))
            per_oligo_dropout.append(dropout_flag)

            coverage_val = ol.metadata.get(RESULT_COVERAGE_KEY)
            coverage_int: int | None
            try:
                coverage_int = int(coverage_val) if coverage_val is not None else None
            except (TypeError, ValueError):
                coverage_int = None
            per_oligo_coverage.append(coverage_int)

            mutations_val = ol.metadata.get(RESULT_MUTATION_TOTALS_KEY)
            mutation_counts: dict[str, int] = {}
            if mutations_val is not None:
                parsed: dict[str, Any] | None
                if isinstance(mutations_val, str):
                    try:
                        parsed = json.loads(mutations_val)
                    except json.JSONDecodeError:
                        parsed = None
                elif isinstance(mutations_val, Mapping):
                    parsed = dict(mutations_val)
                else:
                    parsed = None
                if parsed:
                    for key in ("substitutions", "insertions", "deletions"):
                        try:
                            mutation_counts[key] = int(parsed.get(key, 0))
                        except (TypeError, ValueError):
                            mutation_counts[key] = 0
            per_oligo_mutations.append(mutation_counts)

        dropout_list = per_oligo_dropout or [False] * len(sequences)
        per_oligo_coverage = (
            per_oligo_coverage
            if any(value is not None for value in per_oligo_coverage)
            else [None] * len(sequences)
        )
        per_oligo_mutations = (
            per_oligo_mutations
            if any(mutation_counts for mutation_counts in per_oligo_mutations)
            else [{} for _ in sequences]
        )

        coverage = coverage if coverage is not None else _estimate_coverage(batch)
    else:
        base_sequence = str(dna)
        sequences = list(oligos or [base_sequence])
        dropout_list = list(dropout_flags) if dropout_flags is not None else [False] * len(sequences)
        if len(dropout_list) < len(sequences):
            dropout_list.extend([False] * (len(sequences) - len(dropout_list)))
        per_oligo_coverage = [None] * len(sequences)
        per_oligo_mutations = [{} for _ in sequences]

    gc_content = calculate_gc_content(base_sequence)
    max_homopolymer = get_max_homopolymer_length(base_sequence)
    gc_dist = _gc_distribution(base_sequence)
    hp_runs = _homopolymer_runs(base_sequence)
    gc_variance = (
        sum((val - gc_content) ** 2 for val in gc_dist) / len(gc_dist)
        if gc_dist
        else 0.0
    )

    success = 1.0 if decoded == original_data else 0.0
    constraint_violations: Dict[str, Any]
    try:
        from .synthesis import SynthesisConstraints

        constraint_limits = constraints if constraints is not None else SynthesisConstraints()
        engine = constraint_limits.to_engine()
        violation_records: list[dict[str, Any]] = []
        type_counts: Counter[str] = Counter()

        target_oligos: list[tuple[int, str, dict[str, Any]]] = []
        if batch is not None:
            for idx, oligo in enumerate(primary_oligos, start=1):
                sequence_id = (
                    oligo.metadata.get("oligo_id")
                    or oligo.metadata.get("sequence_id")
                    or oligo.oligo_id
                    or oligo.metadata.get("oligo_index")
                    or f"oligo-{idx}"
                )
                info: dict[str, Any] = {
                    "sequence_id": str(sequence_id),
                    "oligo_index": oligo.metadata.get("oligo_index") or str(idx),
                }
                oligo_id_val = oligo.metadata.get("oligo_id") or oligo.oligo_id
                if oligo_id_val is not None:
                    info["oligo_id"] = str(oligo_id_val)
                target_oligos.append((idx, oligo.sequence, info))
        else:
            for idx, sequence in enumerate(sequences, start=1):
                info = {"sequence_id": f"sequence-{idx}", "oligo_index": str(idx)}
                target_oligos.append((idx, sequence, info))

        for idx, sequence, info in target_oligos:
            report = engine.validate(sequence)
            if report.count == 0:
                continue
            for violation in report.violations:
                violation_type = violation.rule_id
                if violation.rule_id == "gc_range":
                    gc_value = float(violation.details.get("gc_content", 0.0))
                    gc_min = float(violation.details.get("gc_min", 0.0))
                    gc_max = float(violation.details.get("gc_max", 1.0))
                    if gc_value < gc_min:
                        violation_type = "gc_low"
                    elif gc_value > gc_max:
                        violation_type = "gc_high"
                type_counts[violation_type] += 1
                record: dict[str, Any] = {
                    "sequence_id": info.get("sequence_id", f"oligo-{idx}"),
                    "index": idx,
                    "length": len(sequence),
                    "type": violation_type,
                    "constraint": violation.rule_id,
                    "message": violation.message,
                    "severity": violation.severity,
                    "details": violation.details,
                }
                if violation.location is not None:
                    record["location"] = {
                        "start": violation.location.start,
                        "end": violation.location.end,
                    }
                if info.get("oligo_id"):
                    record["oligo_id"] = info["oligo_id"]
                if info.get("oligo_index") is not None:
                    record["oligo_index"] = info["oligo_index"]
                violation_records.append(record)

        opportunities = max(1, sum(len(sequence) for _, sequence, _ in target_oligos))
        constraint_violations = {
            "count": len(violation_records),
            "pressure": len(violation_records) / opportunities,
            "violations": violation_records,
            "type_counts": dict(type_counts),
            "limits": engine.rules.limits(),
        }
    except Exception:  # pragma: no cover - optional dependency
        constraint_violations = {
            "count": 0,
            "violations": [],
            "type_counts": {},
            "limits": {},
        }

    per_oligo_gc = [calculate_gc_content(seq) for seq in sequences]
    per_oligo_hp = [get_max_homopolymer_length(seq) for seq in sequences]

    ecc_map: dict[str, list[float]] = {}
    if ecc_outcomes:
        for name, values in ecc_outcomes.items():
            ratios: list[float] = []
            for value in values:
                if isinstance(value, bool):
                    ratios.append(1.0 if value else 0.0)
                else:
                    try:
                        ratios.append(float(value))
                    except Exception:
                        ratios.append(0.0)
            if ratios:
                ecc_map[str(name)] = ratios

    opportunities = max(0, sum(len(seq) for seq in sequences))
    result: Dict[str, Any] = {
        "gc_distribution": gc_dist,
        "gc_content": gc_content,
        "gc_variance": gc_variance,
        "max_homopolymer": max_homopolymer,
        "homopolymer_runs": hp_runs,
        "ecc_success_rates": {fec: success} if fec else {},
        "decode_success_rate": success,
        "coverage": coverage,
        "constraint_violations": constraint_violations,
        "constraint_outcomes": [dict(item) for item in (constraint_outcomes or ())],
        "error_bases": opportunities,
        "substitution_rate": 0.0,
        "insertion_rate": 0.0,
        "deletion_rate": 0.0,
        "error_rate": 0.0,
        "oligo_metrics": {
            "gc_percentages": per_oligo_gc,
            "max_homopolymers": per_oligo_hp,
            "dropout_flags": [bool(flag) for flag in dropout_list[: len(sequences)]],
            "coverage": per_oligo_coverage,
            "mutation_counts": per_oligo_mutations,
            "ecc_success": ecc_map or ({fec: [success]} if fec else {}),
        },
    }
    normalized_stack = normalize_stack_metrics([], base_sequence)
    if stack_metrics and isinstance(stack_metrics, Mapping):
        normalized_stack = {**normalized_stack, **dict(stack_metrics)}
    result["coding_stack"] = normalized_stack

    if subs is not None and ins is not None and dels is not None:
        denom = max(1, opportunities)
        substitution_rate = float(subs) / denom
        insertion_rate = float(ins) / denom
        deletion_rate = float(dels) / denom
        result.update(
            {
                "substitutions": subs,
                "insertions": ins,
                "deletions": dels,
                "error_bases": opportunities,
                "substitution_rate": substitution_rate,
                "insertion_rate": insertion_rate,
                "deletion_rate": deletion_rate,
                "error_rate": substitution_rate + insertion_rate + deletion_rate,
            }
        )
    return result




def inspect_coding_plan(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return planner diagnostics for why stack candidates were selected/rejected."""

    init_plugins()
    plan = plan_stack_from_config(config)
    return plan.summary()


def compile_coding_stack(config: Mapping[str, Any]) -> list[object]:
    """Validate and compile a declarative coding stack from config."""

    init_plugins()
    return list(compile_stack_from_config(config))

def run_pipeline(
    codec: str,
    fec: str | None,
    channel: str | None,
    input_path: str,
    output_path: str,
) -> Tuple[bytes, Dict[str, Any]]:
    """Process ``input_path`` through the selected codec, FEC and channel.

    The decoded bytes are written to ``output_path`` and also returned.
    """
    original_data = Path(input_path).read_bytes()
    result = run_canonical_pipeline(codec, fec, channel, original_data)
    Path(output_path).write_bytes(result.decoded)
    return result.decoded, result.metrics
