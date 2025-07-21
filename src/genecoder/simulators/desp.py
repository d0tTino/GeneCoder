from __future__ import annotations

"""Simulator wrapper exposing DeSP via the plugin system."""

from typing import Callable

try:  # pragma: no cover - optional dependency
    import desp
    _HAS_DESP = True
except Exception:  # pragma: no cover - missing optional dependency
    _HAS_DESP = False

from . import register_simulator as _register_simulator
from ..channels.base import BaseChannel
from ..error_simulation import introduce_errors
from ..random_utils import make_rng

__all__ = ["DeSPChannel", "register"]


class DeSPChannel(BaseChannel):
    """Channel delegating to the ``desp`` package if installed."""

    def __init__(self, error_rate: float = 0.05) -> None:
        self.error_rate = error_rate

    def simulate(self, sequence: str) -> str:
        if _HAS_DESP:
            if hasattr(desp, "simulate"):
                return str(desp.simulate(sequence, error_rate=self.error_rate))
            raise ImportError("desp.simulate not available")
        return introduce_errors(
            sequence,
            substitution_prob=self.error_rate,
            insertion_prob=0.0,
            deletion_prob=0.0,
            rng=make_rng(),
        )


def register(
    registrar: Callable[[str, BaseChannel], None] = _register_simulator,
) -> None:
    """Register the DeSP simulator."""

    registrar("desp", DeSPChannel())
