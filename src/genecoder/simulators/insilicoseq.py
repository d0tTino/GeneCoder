from __future__ import annotations

"""Simulator wrapper exposing InSilicoSeq via the plugin system."""

from typing import Callable

try:  # pragma: no cover - optional dependency
    from iss.generator import simulate_read
    from iss.error_models.perfect import PerfectErrorModel
    _HAS_ISS = True
except Exception:  # pragma: no cover - missing optional dependency
    _HAS_ISS = False

from . import register_simulator as _register_simulator
from ..channels.base import BaseChannel

__all__ = ["InsilicoSeqChannel", "register"]


class InsilicoSeqChannel(BaseChannel):
    """Channel using InSilicoSeq's perfect error model."""

    def __init__(self, read_length: int = 100) -> None:
        self.read_length = read_length

    def simulate(self, sequence: str) -> str:
        if not _HAS_ISS:
            raise ImportError(
                "insilicoseq is required for this simulator. Install it via 'pip install insilicoseq'."
            )
        _ = PerfectErrorModel()  # load dependency
        return sequence


def register(
    registrar: Callable[[str, BaseChannel], None] = _register_simulator,
) -> None:
    """Register the InSilicoSeq simulator."""

    registrar("insilicoseq", InsilicoSeqChannel())
