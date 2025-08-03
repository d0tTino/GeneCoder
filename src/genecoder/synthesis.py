from __future__ import annotations

"""Helpers for DNA synthesis constraints."""

from dataclasses import dataclass

from .utils import get_max_homopolymer_length


@dataclass
class SynthesisConstraints:
    """Simple synthesis constraints."""

    min_length: int = 25
    max_length: int = 300
    max_homopolymer: int = 4
    gc_min: float = 0.0
    gc_max: float = 1.0

    def __post_init__(self) -> None:
        if self.min_length <= 0:
            raise ValueError("min_length must be greater than 0")
        if self.max_length <= 0:
            raise ValueError("max_length must be greater than 0")
        if self.min_length > self.max_length:
            raise ValueError("min_length cannot be greater than max_length")
        if not 0.0 <= self.gc_min <= 1.0:
            raise ValueError("gc_min must be between 0.0 and 1.0")
        if not 0.0 <= self.gc_max <= 1.0:
            raise ValueError("gc_max must be between 0.0 and 1.0")
        if self.gc_min > self.gc_max:
            raise ValueError("gc_min cannot be greater than gc_max")


def validate_sequence(seq: str, constraints: SynthesisConstraints | None = None) -> bool:
    """Return ``True`` if ``seq`` satisfies ``constraints``."""

    if constraints is None:
        constraints = SynthesisConstraints()

    length = len(seq)
    if length < constraints.min_length or length > constraints.max_length:
        return False
    if get_max_homopolymer_length(seq) > constraints.max_homopolymer:
        return False
    seq_upper = seq.upper()
    gc_content = (seq_upper.count("G") + seq_upper.count("C")) / length if length else 0.0
    if gc_content < constraints.gc_min or gc_content > constraints.gc_max:
        return False
    return True
