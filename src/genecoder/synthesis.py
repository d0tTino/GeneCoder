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

    def __post_init__(self) -> None:
        if self.min_length <= 0:
            raise ValueError("min_length must be greater than 0")
        if self.max_length <= 0:
            raise ValueError("max_length must be greater than 0")
        if self.min_length > self.max_length:
            raise ValueError("min_length cannot be greater than max_length")


def validate_sequence(seq: str, constraints: SynthesisConstraints | None = None) -> bool:
    """Return ``True`` if ``seq`` satisfies ``constraints``."""

    if constraints is None:
        constraints = SynthesisConstraints()

    length = len(seq)
    if length < constraints.min_length or length > constraints.max_length:
        return False
    if get_max_homopolymer_length(seq) > constraints.max_homopolymer:
        return False
    return True
