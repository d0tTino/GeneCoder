from __future__ import annotations

"""Simple encode/ECC/channel/decode pipeline utilities."""

import inspect
import json
import os
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Sequence, Tuple
from typing import get_args, get_origin

from .gc_constrained_encoder import calculate_gc_content
from .utils import get_max_homopolymer_length

from .plugin_manager import CODEC_REGISTRY, FEC_REGISTRY, init_plugins
from .random_utils import reset_rng
from .simulators import SIMULATOR_REGISTRY
from .formats import SequenceBatch, SequenceOligo
from .simulators.batch_utils import (
    RESULT_COVERAGE_KEY,
    RESULT_DROPOUT_FLAG_KEY,
    RESULT_MUTATION_TOTALS_KEY,
)

if TYPE_CHECKING:
    from .synthesis import SynthesisConstraints

__all__ = ["encode", "simulate", "decode", "metrics", "run_pipeline"]


def _annotation_supports_sequence_batch(annotation: object) -> bool:
    """Return ``True`` if ``annotation`` references :class:`SequenceBatch`."""

    if annotation is inspect._empty:
        return False
    if isinstance(annotation, str):
        return "SequenceBatch" in annotation
    origin = get_origin(annotation)
    if origin is not None:
        return any(_annotation_supports_sequence_batch(arg) for arg in get_args(annotation))
    try:
        return bool(annotation is SequenceBatch or issubclass(annotation, SequenceBatch))
    except TypeError:
        return False


def _has_batch_flag(candidate: object) -> bool:
    """Return ``True`` if ``candidate`` advertises batch support."""

    return bool(
        getattr(candidate, "__genecoder_accepts_batch__", False)
        or getattr(candidate, "accepts_sequence_batch", False)
        or getattr(candidate, "supports_sequence_batch", False)
    )


def _codec_accepts_sequence_batch(decode_fn: object) -> bool:
    """Return ``True`` when ``decode_fn`` opts into ``SequenceBatch`` inputs."""

    for candidate in (decode_fn, getattr(decode_fn, "__self__", None), getattr(decode_fn, "__func__", None)):
        if candidate is not None and _has_batch_flag(candidate):
            return True
    try:
        signature = inspect.signature(decode_fn)
    except (TypeError, ValueError):
        return False
    params = list(signature.parameters.values())
    if not params:
        return False
    first_param = params[0]
    return _annotation_supports_sequence_batch(first_param.annotation)



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


def encode(
    codec: str, fec: str | None, data: bytes
) -> Tuple[SequenceBatch, Mapping[str, Any] | None]:
    """Return encoded :class:`SequenceBatch` for ``data`` and optional FEC info."""

    if codec not in CODEC_REGISTRY:
        raise ValueError(f"Unknown codec: {codec}")
    if fec and fec not in FEC_REGISTRY:
        raise ValueError(f"Unknown FEC: {fec}")

    fec_info: Mapping[str, Any] | None = None
    if fec:
        data, fec_info = FEC_REGISTRY[fec]["encode"](data)

    encoded = CODEC_REGISTRY[codec]["encode"](data)
    if isinstance(encoded, SequenceBatch):
        batch = encoded
    elif isinstance(encoded, str):
        batch = _wrap_single_sequence(encoded, batch_id=f"{codec}-batch", codec=codec)
    else:
        raise TypeError(
            "Codec implementations must return a string or SequenceBatch"
        )

    if fec_info is not None:
        info_dict = dict(fec_info)
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
    channel: str | None, dna: SequenceBatch | str
) -> Tuple[SequenceBatch | str, int | None, int | None, int | None, int | None]:
    """Return ``dna`` possibly mutated by ``channel`` and error counts."""

    is_batch = isinstance(dna, SequenceBatch)
    original_batch = dna if is_batch else _wrap_single_sequence(str(dna), batch_id="channel")

    if channel and channel != "none":
        if channel not in SIMULATOR_REGISTRY:
            raise ValueError(f"Unknown channel: {channel}")
        if os.getenv("GENECODER_SIM_SEED") is not None:
            reset_rng()
        sim = SIMULATOR_REGISTRY[channel]
        result = sim.simulate(original_batch)
        mutated_batch = (
            result
            if isinstance(result, SequenceBatch)
            else _wrap_single_sequence(str(result), batch_id=original_batch.batch_id)
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
    survivor_batch: SequenceBatch | None = None,
) -> bytes:
    """Return decoded bytes from ``dna`` applying optional FEC."""

    if codec not in CODEC_REGISTRY:
        raise ValueError(f"Unknown codec: {codec}")

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
            if dropout_flag or (coverage_int is not None and coverage_int <= 0) or mutation_flag:
                continue
            filtered.append(oligo)
        if len(filtered) != len(dna.oligos):
            if filtered:
                batch = SequenceBatch(
                    batch_id=dna.batch_id,
                    metadata=dict(dna.metadata),
                    seed=dna.seed,
                    oligos=list(filtered),
                )
            else:
                batch = dna
    if survivor_batch is None and isinstance(dna, SequenceBatch):
        survivor_batch = dna
    decode_fn = CODEC_REGISTRY[codec]["decode"]
    primary_sequence = batch.primary_sequence()
    if _codec_accepts_sequence_batch(decode_fn):
        decoded_any = decode_fn(
            batch,
            batch_metadata=dict(batch.metadata),
            oligo_metadata=[dict(ol.metadata) for ol in batch.oligos],
        )
    else:
        decoded_any = decode_fn(primary_sequence)
    assert isinstance(decoded_any, (bytes, bytearray))
    decoded = bytes(decoded_any)

    if fec:
        if fec not in FEC_REGISTRY:
            raise ValueError(f"Unknown FEC: {fec}")
        assert fec_info is not None
        combined_info: dict[str, Any] = {"batch_id": batch.batch_id, **batch.metadata}
        combined_info.update(fec_info)
        fec_kwargs: dict[str, Any] = {}
        if survivor_batch is not None:
            fec_kwargs["survivor_batch"] = survivor_batch
        decoded, _ = FEC_REGISTRY[fec]["decode"](decoded, combined_info, **fec_kwargs)

    return decoded


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
        from .synthesis import SynthesisConstraints, validate_sequence

        constraint_limits = constraints or SynthesisConstraints()
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
            try:
                is_valid = validate_sequence(sequence, constraint_limits)
            except Exception:
                continue
            if is_valid:
                continue

            reasons: list[str] = []
            length = len(sequence)
            if length < constraint_limits.min_length:
                reasons.append("length_short")
            elif length > constraint_limits.max_length:
                reasons.append("length_long")

            homopolymer = get_max_homopolymer_length(sequence)
            if homopolymer > constraint_limits.max_homopolymer:
                reasons.append("homopolymer")

            gc_fraction = calculate_gc_content(sequence) if sequence else 0.0
            if gc_fraction < constraint_limits.gc_min:
                reasons.append("gc_low")
            elif gc_fraction > constraint_limits.gc_max:
                reasons.append("gc_high")

            if not reasons:
                reasons.append("unknown")

            for name in reasons:
                type_counts[name] += 1

            record: dict[str, Any] = {
                "sequence_id": info.get("sequence_id", f"oligo-{idx}"),
                "index": idx,
                "length": length,
                "type": reasons[0],
            }
            if len(reasons) > 1:
                record["types"] = reasons
            if info.get("oligo_id"):
                record["oligo_id"] = info["oligo_id"]
            if info.get("oligo_index") is not None:
                record["oligo_index"] = info["oligo_index"]
            violation_records.append(record)

        constraint_violations = {
            "count": len(violation_records),
            "violations": violation_records,
            "type_counts": dict(type_counts),
        }
    except Exception:  # pragma: no cover - optional dependency
        constraint_violations = {"count": 0, "violations": [], "type_counts": {}}

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
        "oligo_metrics": {
            "gc_percentages": per_oligo_gc,
            "max_homopolymers": per_oligo_hp,
            "dropout_flags": [bool(flag) for flag in dropout_list[: len(sequences)]],
            "coverage": per_oligo_coverage,
            "mutation_counts": per_oligo_mutations,
            "ecc_success": ecc_map or ({fec: [success]} if fec else {}),
        },
    }
    if subs is not None and ins is not None and dels is not None:
        result.update({"substitutions": subs, "insertions": ins, "deletions": dels})
    return result


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
    init_plugins()
    if os.getenv("GENECODER_SIM_SEED") is not None:
        reset_rng()

    original_data = Path(input_path).read_bytes()
    dna_batch, fec_info = encode(codec, fec, original_data)
    simulated, subs, ins, dels, coverage = simulate(channel, dna_batch)
    batch_result = simulated if isinstance(simulated, SequenceBatch) else _wrap_single_sequence(simulated)
    survivor_batch = batch_result if isinstance(batch_result, SequenceBatch) else None
    decoded = decode(
        codec,
        fec,
        batch_result,
        fec_info,
        survivor_batch=survivor_batch,
    )

    Path(output_path).write_bytes(decoded)
    metrics_dict = metrics(
        batch_result,
        original_data,
        decoded,
        fec,
        subs,
        ins,
        dels,
        coverage,
    )
    return decoded, metrics_dict
