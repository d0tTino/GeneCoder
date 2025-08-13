"""Utilities to modify DNA sequences to satisfy synthesis constraints."""

from __future__ import annotations

import random

from .random_utils import make_rng

__all__ = ["adjust_gc_balance", "limit_homopolymers", "fix_sequence"]


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
