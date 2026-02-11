"""Constraint fixer backed by the pluggable solver engine."""
# ruff: noqa: ANN401

from __future__ import annotations

from typing import Any, Callable

from .api import Codec
from .constraint_fixer import fix_sequence_with_report

__all__ = ["fix_sequence_dnachisel", "register"]


def fix_sequence_dnachisel(
    sequence: str,
    *,
    gc_min: float,
    gc_max: float,
    max_homopolymer: int,
) -> str:
    fixed, _report = fix_sequence_with_report(
        sequence,
        target_gc_min=gc_min,
        target_gc_max=gc_max,
        max_homopolymer=max_homopolymer,
        strategy="external_solver",
    )
    return fixed


class _DummyCodec(Codec):
    def encode(self, data: bytes, /, **kwargs: Any) -> str:  # pragma: no cover
        return ""

    def decode(self, encoded: str, /, **kwargs: Any) -> bytes:  # pragma: no cover
        return b""


def register(register_codec: Callable[[str, type[Codec]], None]) -> None:
    register_codec("dnachisel_fixer", _DummyCodec)
