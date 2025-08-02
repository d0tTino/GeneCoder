from __future__ import annotations

"""Simple encode/ECC/channel/decode pipeline utilities."""

from pathlib import Path
from typing import Any, Mapping, Tuple, Dict, List
from difflib import SequenceMatcher

from .gc_constrained_encoder import calculate_gc_content
from .utils import get_max_homopolymer_length

from .plugin_manager import CODEC_REGISTRY, FEC_REGISTRY, init_plugins
from .simulators import SIMULATOR_REGISTRY

__all__ = ["run_pipeline"]


def _count_errors(original: str, mutated: str) -> tuple[int, int, int]:
    """Return substitution, insertion and deletion counts."""
    subs = ins = dels = 0
    sm = SequenceMatcher(None, original, mutated)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace":
            subs += max(i2 - i1, j2 - j1)
        elif tag == "delete":
            dels += i2 - i1
        elif tag == "insert":
            ins += j2 - j1
    return subs, ins, dels


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
    if channel and channel != "none":
        dna = SIMULATOR_REGISTRY[channel].simulate(dna)
        subs, ins, dels = _count_errors(orig_dna, dna)

    gc_content = calculate_gc_content(dna)
    max_homopolymer = get_max_homopolymer_length(dna)
    gc_dist = _gc_distribution(dna)
    hp_runs = _homopolymer_runs(dna)

    decoded_any = CODEC_REGISTRY[codec]["decode"](dna)
    assert isinstance(decoded_any, (bytes, bytearray))
    decoded = bytes(decoded_any)

    if fec:
        assert fec_info is not None
        decoded, _ = FEC_REGISTRY[fec]["decode"](decoded, fec_info)

    Path(output_path).write_bytes(decoded)
    success = 1.0 if decoded == original_data else 0.0
    metrics: Dict[str, Any] = {
        "gc_distribution": gc_dist,
        "gc_content": gc_content,
        "max_homopolymer": max_homopolymer,
        "homopolymer_runs": hp_runs,
        "ecc_success_rates": {fec: success} if fec else {},
        "decode_success_rate": success,
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
