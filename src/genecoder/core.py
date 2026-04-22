from __future__ import annotations

"""Simple encode/ECC/channel/decode pipeline utilities."""

import json
import time
import warnings
from collections import Counter
from pathlib import Path
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Sequence, Tuple

from .gc_constrained_encoder import calculate_gc_content
from .utils import get_max_homopolymer_length

from .plugin_manager import init_plugins
from .runtime import RunContext, make_run_context
from .coding.stack import normalize_stack_metrics
from .compat.coding_stack import (
    compile_coding_stack_from_config,
    plan_coding_stack,
)
from .formats import SequenceBatch
from .constraints import ConstraintPolicy
from .runtime.models import DecodeStageInput, EncodeStageInput, SimulateStageInput
from .runtime.stages import (
    DecodeStageService,
    EncodeStageService,
    SimulateStageService,
    batch_for_decode,
    estimate_coverage,
    parse_bool,
    wrap_single_sequence,
)
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
    "MODERN_INDEL_PROFILES",
    "LEGACY_INDEL_PROFILE_ALIASES",
    "LEGACY_INDEL_PROFILE_NAMES",
    "LEGACY_DEFAULT_INDEL_PROFILE",
    "resolve_indel_profile",
]

ORCHESTRATION_DEPRECATION_GATE = "v0.18.0"

MODERN_INDEL_PROFILES: dict[str, dict[str, float]] = {
    "illumina": {
        "substitution_prob": 0.002,
        "insertion_prob": 0.0001,
        "deletion_prob": 0.0001,
    },
    "nanopore": {
        "substitution_prob": 0.01,
        "insertion_prob": 0.02,
        "deletion_prob": 0.02,
    },
}

LEGACY_INDEL_PROFILE_ALIASES: dict[str, str] = {
    "illumina_adapter": "illumina",
    "nanopore_adapter": "nanopore",
}

LEGACY_INDEL_PROFILE_NAMES: set[str] = set(LEGACY_INDEL_PROFILE_ALIASES)
LEGACY_DEFAULT_INDEL_PROFILE: str = "illumina_adapter"


def resolve_indel_profile(
    *,
    requested_profile: str | None,
    has_explicit_rates: bool,
) -> tuple[str | None, list[str]]:
    profile_warnings: list[str] = []
    profile = requested_profile
    if profile is None and not has_explicit_rates:
        profile = LEGACY_DEFAULT_INDEL_PROFILE
        profile_warnings.append(
            "Using legacy implicit indel default profile; migrate to --simulator indel --indel-profile illumina."
        )
    if profile is None:
        return None, profile_warnings

    lowered = profile.lower()
    if lowered in LEGACY_INDEL_PROFILE_ALIASES:
        profile_warnings.append(
            f"Legacy indel profile '{profile}' is deprecated; using '{LEGACY_INDEL_PROFILE_ALIASES[lowered]}' instead."
        )
        return LEGACY_INDEL_PROFILE_ALIASES[lowered], profile_warnings
    if lowered in MODERN_INDEL_PROFILES:
        if requested_profile is not None:
            profile_warnings.append(
                "--indel-profile is a compatibility flag and may be removed; prefer simulator config in workflow YAML."
            )
        return lowered, profile_warnings
    raise ValueError(f"Unknown indel profile: {profile}")


def _warn_orchestration_deprecation(name: str) -> None:
    warnings.warn(
        (
            f"genecoder.core.{name} is a compatibility facade and will be removed in "
            f"{ORCHESTRATION_DEPRECATION_GATE}; use genecoder.app.RunPipelineUseCase instead."
        ),
        DeprecationWarning,
        stacklevel=3,
    )


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
    runtime: Mapping[str, float]



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
    return wrap_single_sequence(sequence, batch_id=batch_id, codec=codec)


def encode(
    codec: str,
    fec: str | None,
    data: bytes,
    *,
    constraint_policy: ConstraintPolicy | None = None,
    run_context: RunContext | None = None,
) -> Tuple[SequenceBatch, Mapping[str, Any] | None]:
    """Return encoded :class:`SequenceBatch` for ``data`` and optional FEC info."""
    output = EncodeStageService().run(
        EncodeStageInput(
            codec=codec,
            fec=fec,
            data=data,
            constraint_policy=constraint_policy,
            run_context=run_context,
        )
    )
    return output.encoded_batch, output.fec_info


def _parse_bool(value: object) -> bool:
    return parse_bool(value)


def _batch_for_decode(batch: SequenceBatch, *, filter_mutated: bool) -> SequenceBatch:
    return batch_for_decode(batch, filter_mutated=filter_mutated)


def run_canonical_pipeline(
    codec: str,
    fec: str | None,
    channel: str | None,
    original_data: bytes,
    *,
    filter_mutated: bool = False,
    channel_parameters: Mapping[str, Any] | None = None,
    run_context: RunContext | None = None,
) -> CanonicalRuntimeResult:
    """Execute the canonical internal runtime route: encode → simulate → decode."""

    _warn_orchestration_deprecation("run_canonical_pipeline")

    init_plugins()
    runtime_context = run_context or make_run_context()

    total_started_at = time.perf_counter()

    encode_service = EncodeStageService()
    simulate_service = SimulateStageService()
    decode_service = DecodeStageService()

    encode_started_at = time.perf_counter()
    encode_result = encode_service.run(
        EncodeStageInput(codec=codec, fec=fec, data=original_data, run_context=runtime_context)
    )
    encoded_batch = encode_result.encoded_batch
    fec_info = encode_result.fec_info
    encode_seconds = time.perf_counter() - encode_started_at

    simulate_started_at = time.perf_counter()
    simulate_result = simulate_service.run(
        SimulateStageInput(
            channel=channel,
            dna=encoded_batch,
            channel_parameters=channel_parameters,
            run_context=runtime_context,
        )
    )
    simulate_seconds = time.perf_counter() - simulate_started_at

    simulated_batch = (
        simulate_result.dna
        if isinstance(simulate_result.dna, SequenceBatch)
        else _wrap_single_sequence(str(simulate_result.dna))
    )
    decode_input = _batch_for_decode(simulated_batch, filter_mutated=filter_mutated)

    decode_started_at = time.perf_counter()
    decode_result = decode_service.run(
        DecodeStageInput(
            codec=codec,
            fec=fec,
            dna=decode_input,
            fec_info=fec_info,
            filter_mutated=filter_mutated,
            survivor_batch=decode_input,
            run_context=runtime_context,
        )
    )
    decode_seconds = time.perf_counter() - decode_started_at

    metrics_dict = metrics(
        simulated_batch,
        original_data,
        decode_result.decoded,
        fec,
        simulate_result.substitutions,
        simulate_result.insertions,
        simulate_result.deletions,
        simulate_result.coverage,
        stack_metrics=(dict(fec_info).get("coding_stack") if isinstance(fec_info, Mapping) else None),
        constraint_outcomes=(
            dict(fec_info).get("constraint_outcomes") if isinstance(fec_info, Mapping) else None
        ),
    )
    total_seconds = time.perf_counter() - total_started_at

    return CanonicalRuntimeResult(
        original_data=original_data,
        encoded_batch=encoded_batch,
        simulated_batch=simulated_batch,
        decode_input=decode_input,
        survivor_batch=decode_input,
        decoded=decode_result.decoded,
        metrics=metrics_dict,
        fec_info=fec_info,
        substitutions=simulate_result.substitutions,
        insertions=simulate_result.insertions,
        deletions=simulate_result.deletions,
        coverage=simulate_result.coverage,
        runtime={
            "total_seconds": total_seconds,
            "encode_seconds": encode_seconds,
            "simulate_seconds": simulate_seconds,
            "decode_seconds": decode_seconds,
        },
    )


def _estimate_coverage(batch: SequenceBatch) -> int | None:
    return estimate_coverage(batch)


def simulate(
    channel: str | None,
    dna: SequenceBatch | str,
    *,
    channel_parameters: Mapping[str, Any] | None = None,
    run_context: RunContext | None = None,
) -> Tuple[SequenceBatch | str, int | None, int | None, int | None, int | None]:
    """Return ``dna`` possibly mutated by ``channel`` and error counts."""
    output = SimulateStageService().run(
        SimulateStageInput(
            channel=channel,
            dna=dna,
            channel_parameters=channel_parameters,
            run_context=run_context,
        )
    )
    return (
        output.dna,
        output.substitutions,
        output.insertions,
        output.deletions,
        output.coverage,
    )


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

    output = DecodeStageService().run(
        DecodeStageInput(
            codec=codec,
            fec=fec,
            dna=dna,
            fec_info=fec_info,
            filter_mutated=filter_mutated,
            survivor_batch=survivor_batch,
            constraint_policy=constraint_policy,
            run_context=run_context,
        )
    )
    return output.decoded


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
    constraint_outcomes: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Return quality metrics for ``dna`` and decode results."""

    batch = dna if isinstance(dna, SequenceBatch) else None
    if batch is not None:
        base_sequence = batch.combined_sequence()
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

    if constraint_outcomes is None and batch is not None:
        batch_outcomes = batch.metadata.get("constraint_outcomes")
        if isinstance(batch_outcomes, Mapping):
            constraint_outcomes = dict(batch_outcomes)

    by_oligo_outcomes = (
        dict(constraint_outcomes.get("by_oligo", {}))
        if isinstance(constraint_outcomes, Mapping)
        else {}
    )
    aggregate_before = 0
    aggregate_after = 0
    if by_oligo_outcomes:
        aggregate_before = sum(int(item.get("violations_before", 0)) for item in by_oligo_outcomes.values() if isinstance(item, Mapping))
        aggregate_after = sum(int(item.get("violations_after", 0)) for item in by_oligo_outcomes.values() if isinstance(item, Mapping))

    opportunities = max(0, sum(len(seq) for seq in sequences))
    objective_stage = {}
    if isinstance(constraint_outcomes, Mapping):
        stages = constraint_outcomes.get("stages")
        if isinstance(stages, list) and stages and isinstance(stages[0], Mapping):
            objective_stage = dict(stages[0])

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
        "constraint_pressure": {
            "aggregate": {
                "before": aggregate_before,
                "after": aggregate_after,
                "violations": constraint_violations.get("count", 0),
                "pressure": constraint_violations.get("pressure", 0.0),
            },
            "by_oligo": by_oligo_outcomes,
        },
        "constraint_outcomes": dict(constraint_outcomes) if isinstance(constraint_outcomes, Mapping) else {},
        "objective_score": objective_stage.get("objective_score"),
        "objective_tradeoff_report": objective_stage.get("objective_tradeoff", {}),
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
    plan = plan_coding_stack(config)
    return plan.summary()


def compile_coding_stack(config: Mapping[str, Any]) -> list[object]:
    """Validate and compile a declarative coding stack from config."""

    init_plugins()
    return list(compile_coding_stack_from_config(config))

def run_pipeline(
    codec: str,
    fec: str | None,
    channel: str | None,
    input_path: str,
    output_path: str,
    channel_parameters: Mapping[str, Any] | None = None,
) -> Tuple[bytes, Dict[str, Any]]:
    """Process ``input_path`` through the selected codec, FEC and channel.

    The decoded bytes are written to ``output_path`` and also returned.
    """
    _warn_orchestration_deprecation("run_pipeline")
    original_data = Path(input_path).read_bytes()
    result = run_canonical_pipeline(codec, fec, channel, original_data, channel_parameters=channel_parameters)
    Path(output_path).write_bytes(result.decoded)
    return result.decoded, result.metrics
