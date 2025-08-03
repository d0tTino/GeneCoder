"""Adapter for the optional ``dnarsim`` read simulator."""
from __future__ import annotations

import random
from typing import Callable

from .api import Simulator
from .random_utils import make_rng
from .nanopore_sim import _simulate_adapter
from .simulator_utils import _run_external
from .simulators import register_simulator as _register_simulator


class _DNARSIM:
    """Internal helper to invoke the :mod:`dnarsim` binary."""

    command = "dnarsim"

    @staticmethod
    def run(sequence: str) -> str:
        """Run ``dnarsim`` on ``sequence`` via :func:`_run_external`."""

        return _run_external(_DNARSIM.command, sequence)


def simulate_dnarsim(
    sequence: str,
    error_rate: float = 0.05,
    rng: random.Random | None = None,
    profile: str | None = None,
) -> str:
    """Use ``dnarsim`` if available, else fall back to :func:`simulate_errors`."""

    if rng is None:
        rng = make_rng()

    extra = ["-p", profile] if profile else None
    return _simulate_adapter("dnarsim", sequence, error_rate, rng, extra)


class DNArSimChannel(Simulator):
    """Channel wrapper for the optional ``dnarsim`` simulator."""

    def __init__(self, error_rate: float = 0.05, profile: str | None = None) -> None:
        self.error_rate = error_rate
        self.profile = profile

    def simulate(self, sequence: str) -> str:
        return simulate_dnarsim(
            sequence,
            error_rate=self.error_rate,
            rng=make_rng(),
            profile=self.profile,
        )

    def with_profile(self, profile: str) -> "DNArSimChannel":
        """Return a new channel configured to use ``profile``."""

        return type(self)(error_rate=self.error_rate, profile=profile)


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    """Register the ``dnarsim`` simulator."""

    registrar("dnarsim", DNArSimChannel())
