from __future__ import annotations

"""Simple encode/ECC/channel/decode pipeline utilities."""

from pathlib import Path
from typing import Any, Mapping, Tuple, Dict
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


def run_pipeline(
    codec: str,
    fec: str | None,
    channel: str | None,
    input_path: str,
    output_path: str,
) -> Tuple[bytes, Dict[str, float | int]]:
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

    data = Path(input_path).read_bytes()

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

    decoded_any = CODEC_REGISTRY[codec]["decode"](dna)
    assert isinstance(decoded_any, (bytes, bytearray))
    decoded = bytes(decoded_any)

    if fec:
        assert fec_info is not None
        decoded, _ = FEC_REGISTRY[fec]["decode"](decoded, fec_info)

    Path(output_path).write_bytes(decoded)
    metrics: Dict[str, float | int] = {
        "gc_content": gc_content,
        "max_homopolymer": max_homopolymer,
    }
    if subs is not None and ins is not None and dels is not None:
        metrics.update({
            "substitutions": subs,
            "insertions": ins,
            "deletions": dels,
        })
    return decoded, metrics
