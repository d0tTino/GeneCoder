from __future__ import annotations

"""Simulator wrapper exposing InSilicoSeq via the plugin system."""

from typing import Callable

try:  # pragma: no cover - optional dependency
    from iss.generator import simulate_read
    _HAS_ISS = True
except Exception:  # pragma: no cover - missing optional dependency
    _HAS_ISS = False

from . import register_simulator as _register_simulator
from ..channels.base import BaseChannel

__all__ = ["InsilicoSeqChannel", "register"]


class InsilicoSeqChannel(BaseChannel):
    """Channel using InSilicoSeq with selectable error models."""

    def __init__(self, read_length: int = 100, profile: str = "hiseq") -> None:
        self.read_length = read_length
        self.profile = profile

    def simulate(self, sequence: str) -> str:
        if not _HAS_ISS:
            raise ImportError(
                "insilicoseq is required for this simulator. Install it via 'pip install insilicoseq'."
            )
        result = simulate_read(sequence, model=self.profile, n_reads=1, read_length=self.read_length)
        if isinstance(result, (list, tuple)):
            return str(result[0])
        return str(result)


def register(
    registrar: Callable[[str, BaseChannel], None] = _register_simulator,
) -> None:
    """Register the InSilicoSeq simulator."""

    registrar("insilicoseq", InsilicoSeqChannel())
