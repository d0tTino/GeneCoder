from __future__ import annotations

"""Simple encode/ECC/channel/decode pipeline utilities."""

from pathlib import Path
from typing import Any, Mapping, Tuple, Dict, List

from .gc_constrained_encoder import calculate_gc_content
from .utils import get_max_homopolymer_length

from .plugin_manager import CODEC_REGISTRY, FEC_REGISTRY, init_plugins
from .simulators import SIMULATOR_REGISTRY

__all__ = ["run_pipeline"]



def _levenshtein_counts(original: str, mutated: str) -> tuple[int, int, int]:
    """Return substitution, insertion and deletion counts using Levenshtein ops."""
    try:  # Prefer the optimized python-Levenshtein package if available
        from Levenshtein import editops

        ops = editops(original, mutated)

        def get_tag(op: Any) -> str:  # noqa: D401,ANN401
            return str(op[0])

    except Exception:  # pragma: no cover - fallback to rapidfuzz
        from rapidfuzz.distance import Levenshtein as RF

        ops = RF.editops(original, mutated)

        def get_tag(op: Any) -> str:  # noqa: D401,ANN401
            return str(op.tag)

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

    if codec not in CODEC_REGISTRY:
        raise ValueError(f"Unknown codec: {codec}")
    if fec and fec not in FEC_REGISTRY:
        raise ValueError(f"Unknown FEC: {fec}")
    if channel and channel != "none" and channel not in SIMULATOR_REGISTRY:
        raise ValueError(f"Unknown channel: {channel}")

    original_data = Path(input_path).read_bytes()
    data = original_data

    fec_info: Mapping[str, Any] | None = None
    if fec:
        data, fec_info = FEC_REGISTRY[fec]["encode"](data)

    dna = CODEC_REGISTRY[codec]["encode"](data)
    orig_dna = dna
    subs = ins = dels = None
    coverage = None
    if channel and channel != "none":
        sim = SIMULATOR_REGISTRY[channel]
        dna = sim.simulate(dna)
        subs, ins, dels = _levenshtein_counts(orig_dna, dna)
        cov_func = getattr(sim, "get_coverage", None)
        if callable(cov_func):
            try:
                coverage = int(cov_func(orig_dna))
            except Exception:
                coverage = None

    gc_content = calculate_gc_content(dna)
    max_homopolymer = get_max_homopolymer_length(dna)
    gc_dist = _gc_distribution(dna)
    hp_runs = _homopolymer_runs(dna)
    gc_variance = (
        sum((val - gc_content) ** 2 for val in gc_dist) / len(gc_dist)
        if gc_dist
        else 0.0
    )

    decoded_any = CODEC_REGISTRY[codec]["decode"](dna)
    assert isinstance(decoded_any, (bytes, bytearray))
    decoded = bytes(decoded_any)

    if fec:
        assert fec_info is not None
        decoded, _ = FEC_REGISTRY[fec]["decode"](decoded, fec_info)

    Path(output_path).write_bytes(decoded)
    success = 1.0 if decoded == original_data else 0.0
    constraint_violations = 0
    try:
        from .synthesis import validate_sequence

        if not validate_sequence(dna):
            constraint_violations = 1
    except Exception:
        constraint_violations = 0

    metrics: Dict[str, Any] = {
        "gc_distribution": gc_dist,
        "gc_content": gc_content,
        "gc_variance": gc_variance,
        "max_homopolymer": max_homopolymer,
        "homopolymer_runs": hp_runs,
        "ecc_success_rates": {fec: success} if fec else {},
        "decode_success_rate": success,
        "coverage": coverage,
        "constraint_violations": constraint_violations,
    }
    if subs is not None and ins is not None and dels is not None:
        metrics.update(
            {
                "substitutions": subs,
                "insertions": ins,
                "deletions": dels,
            }
        )
    return decoded, metrics
