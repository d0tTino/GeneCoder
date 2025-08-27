from __future__ import annotations

"""Simple pipeline for processing sequences step by step."""

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Tuple

from .gc_constrained_encoder import calculate_gc_content
from .plugin_manager import CODEC_REGISTRY, FEC_REGISTRY, init_plugins
from .simulators import SIMULATOR_REGISTRY
from .utils import get_max_homopolymer_length
from .parallel import parallel_map

__all__ = ["SequencePipeline", "run_pipeline"]


def _levenshtein_counts(original: str, mutated: str) -> Tuple[int, int, int]:
    """Return substitution, insertion and deletion counts."""
    try:
        from Levenshtein import editops

        ops = editops(original, mutated)

        def get_tag(op: Any) -> str:  # noqa: D401,ANN401
            return str(op[0])

    except Exception:  # pragma: no cover - fallback
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


class SequencePipeline:
    """Process sequences through a series of transformation steps."""

    def __init__(self, steps: Iterable[Callable[[str], str]] | None = None) -> None:
        self.steps: list[Callable[[str], str]] = list(steps or [])

    def add_step(self, step: Callable[[str], str]) -> None:
        """Append ``step`` to the pipeline."""
        self.steps.append(step)

    def run(self, sequence: str) -> str:
        """Return ``sequence`` processed by each step."""
        for step in self.steps:
            sequence = step(sequence)
        return sequence

    def run_batch(
        self,
        sequences: Sequence[str],
        *,
        parallel: bool = False,
        workers: int | None = None,
        use_processes: bool = False,
    ) -> list[str]:
        """Apply the pipeline to ``sequences`` optionally in parallel."""
        if parallel:
            return parallel_map(
                self.run,
                sequences,
                workers=workers,
                use_processes=use_processes,
            )
        return [self.run(s) for s in sequences]


def run_pipeline(
    codec: str,
    fec_backend: str | None,
    channel: str | None,
    input_path: str,
    output_path: str,
) -> Tuple[bytes, Dict[str, Any], Mapping[str, Any] | None]:
    """Process ``input_path`` through the selected codec, FEC and channel."""

    init_plugins()

    if codec not in CODEC_REGISTRY:
        raise ValueError(f"Unknown codec: {codec}")
    if fec_backend and fec_backend not in FEC_REGISTRY:
        raise ValueError(f"Unknown FEC: {fec_backend}")
    if channel and channel != "none" and channel not in SIMULATOR_REGISTRY:
        raise ValueError(f"Unknown channel: {channel}")

    original_data = Path(input_path).read_bytes()
    data = original_data

    fec_info: Mapping[str, Any] | None = None
    if fec_backend:
        data, fec_info = FEC_REGISTRY[fec_backend]["encode"](data)

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

    if fec_backend:
        assert fec_info is not None
        decoded, _ = FEC_REGISTRY[fec_backend]["decode"](decoded, fec_info)

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
        "ecc_success_rates": {fec_backend: success} if fec_backend else {},
        "decode_success_rate": success,
        "coverage": coverage,
        "constraint_violations": constraint_violations,
    }
    if subs is not None and ins is not None and dels is not None:
        metrics.update({"substitutions": subs, "insertions": ins, "deletions": dels})

    return decoded, metrics, fec_info

