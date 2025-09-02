"""Utilities to modify DNA sequences to satisfy synthesis constraints.

This module exposes small helpers for adjusting GC balance and disrupting
excessive homopolymers.  The high-level :func:`fix` convenience function ties
these helpers together and is designed for use directly from the main encoding
pipeline or CLI, allowing sequences to be automatically corrected before they
are passed along for synthesis.
"""

from __future__ import annotations

import random

from .gc_constrained_encoder import calculate_gc_content
from .utils import get_max_homopolymer_length
from .random_utils import make_rng

__all__ = [
    "adjust_gc_balance",
    "limit_homopolymers",
    "fix_sequence",
    "fix",
    "encode",
]


def adjust_gc_balance(
    sequence: str,
    target_gc_min: float,
    target_gc_max: float,
    *,
    rng: random.Random | None = None,
) -> str:
    """Return ``sequence`` adjusted so its GC content falls within bounds."""
    if target_gc_min > target_gc_max:
        msg = "target_gc_min cannot exceed target_gc_max"
        raise ValueError(msg)

    if rng is None:
        rng = make_rng()
    seq = list(sequence.upper())
    length = len(seq)
    gc_count = sum(1 for b in seq if b in {"G", "C"})
    gc = gc_count / length if length else 0.0
    while gc < target_gc_min:
        idxs = [i for i, b in enumerate(seq) if b in {"A", "T"}]
        if not idxs:
            break
        i = rng.choice(idxs)
        seq[i] = rng.choice(["G", "C"])
        gc_count += 1
        gc = gc_count / length
    while gc > target_gc_max:
        idxs = [i for i, b in enumerate(seq) if b in {"G", "C"}]
        if not idxs:
            break
        i = rng.choice(idxs)
        seq[i] = rng.choice(["A", "T"])
        gc_count -= 1
        gc = gc_count / length
    return "".join(seq)


def limit_homopolymers(
    sequence: str,
    max_len: int,
    *,
    rng: random.Random | None = None,
) -> str:
    """Return ``sequence`` with runs longer than ``max_len`` disrupted."""
    if max_len < 1:
        msg = "max_len must be at least 1"
        raise ValueError(msg)

    if rng is None:
        rng = make_rng()
    seq = list(sequence.upper())
    i = 0
    while i < len(seq):
        run_char = seq[i]
        run_end = i + 1
        while run_end < len(seq) and seq[run_end] == run_char:
            run_end += 1
        run_len = run_end - i
        if run_len > max_len:
            insert_pos = i + max_len
            replacement = {
                "A": ["C", "G"],
                "T": ["A", "C"],
                "G": ["A", "T"],
                "C": ["G", "T"],
            }[run_char]
            seq[insert_pos] = rng.choice(replacement)
            run_end = insert_pos + 1
        i = run_end
    return "".join(seq)


def fix_sequence(
    sequence: str,
    *,
    target_gc_min: float,
    target_gc_max: float,
    max_homopolymer: int,
    rng: random.Random | None = None,
) -> str:
    """Return ``sequence`` adjusted for GC content and homopolymers."""
    if target_gc_min > target_gc_max:
        msg = "target_gc_min cannot exceed target_gc_max"
        raise ValueError(msg)
    if max_homopolymer < 1:
        msg = "max_homopolymer must be at least 1"
        raise ValueError(msg)

    if rng is None:
        rng = make_rng()

    seq = adjust_gc_balance(sequence, target_gc_min, target_gc_max, rng=rng)
    seq = limit_homopolymers(seq, max_homopolymer, rng=rng)
    # Breaking up long homopolymers can skew the GC ratio slightly. Run a final
    # pass of GC balancing to ensure the sequence ends within the requested
    # bounds.
    seq = adjust_gc_balance(seq, target_gc_min, target_gc_max, rng=rng)
    return seq


def fix(
    sequence: str,
    *,
    gc_min: float,
    gc_max: float,
    max_homopolymer: int,
    rng: random.Random | None = None,
) -> str:
    """Return ``sequence`` fixed for GC content and homopolymer limits.

    This convenience wrapper uses shorter parameter names to integrate
    smoothly with the main encoding pipeline.
    """

    return fix_sequence(
        sequence,
        target_gc_min=gc_min,
        target_gc_max=gc_max,
        max_homopolymer=max_homopolymer,
        rng=rng,
    )


def encode(
    sequence: str,
    *,
    gc_min: float,
    gc_max: float,
    max_homopolymer: int,
    rng: random.Random | None = None,
) -> tuple[str, dict[str, float]]:
    """Return a fixed sequence along with GC and homopolymer metrics."""
    fixed = fix_sequence(
        sequence,
        target_gc_min=gc_min,
        target_gc_max=gc_max,
        max_homopolymer=max_homopolymer,
        rng=rng,
    )
    metrics = {
        "gc_content": calculate_gc_content(fixed),
        "max_homopolymer": get_max_homopolymer_length(fixed),
    }
    return fixed, metrics
