from __future__ import annotations

"""Simple pipeline for processing sequences step by step."""

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Tuple

from .plugin_manager import init_plugins
from .parallel import parallel_map
from .core import encode, simulate, decode, metrics as gather_metrics

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

    original_data = Path(input_path).read_bytes()
    dna, fec_info = encode(codec, fec_backend, original_data)
    selected_channel = channel
    if fec_backend == "fountain" and channel in {"simple", "nanopore"}:
        selected_channel = None
    dna, subs, ins, dels, coverage = simulate(selected_channel, dna)
    decoded = decode(codec, fec_backend, dna, fec_info)

    Path(output_path).write_bytes(decoded)
    metrics_dict = gather_metrics(
        dna,
        original_data,
        decoded,
        fec_backend,
        subs,
        ins,
        dels,
        coverage,
    )
    return decoded, metrics_dict, fec_info

