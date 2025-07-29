"""Constraint fixer powered by DNA Chisel."""
# ruff: noqa: ANN401

from __future__ import annotations

from typing import Any, Callable

try:  # optional dependency
    from dnachisel import DnaOptimizationProblem, EnforceGCContent, AvoidPattern
except Exception:  # pragma: no cover - optional dependency missing
    DnaOptimizationProblem = None
    EnforceGCContent = None
    AvoidPattern = None

from .api import Codec

__all__ = ["fix_sequence_dnachisel", "register"]


def fix_sequence_dnachisel(
    sequence: str,
    *,
    gc_min: float,
    gc_max: float,
    max_homopolymer: int,
) -> str:
    """Return ``sequence`` fixed for GC and homopolymers using DNA Chisel."""
    if DnaOptimizationProblem is None:
        raise ImportError("dnachisel is required for fix_sequence_dnachisel")
    constraints = [EnforceGCContent(mini=gc_min, maxi=gc_max)]
    if max_homopolymer >= 1:
        for base in "ATGC":
            constraints.append(AvoidPattern(base * (max_homopolymer + 1)))
    problem = DnaOptimizationProblem(
        sequence=sequence.upper(),
        constraints=constraints,
        logger=None,
    )
    problem.resolve_constraints()
    return str(problem.sequence)


class _DummyCodec(Codec):
    """Minimal codec used only for plugin registration."""

    def encode(self, data: bytes, /, **kwargs: Any) -> str:  # pragma: no cover - unused
        return ""

    def decode(self, encoded: str, /, **kwargs: Any) -> bytes:  # pragma: no cover - unused
        return b""


def register(register_codec: Callable[[str, type[Codec]], None]) -> None:
    """Register this module's dummy codec with ``register_codec``."""

    register_codec("dnachisel_fixer", _DummyCodec)
