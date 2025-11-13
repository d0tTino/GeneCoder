"""Adapter for the optional ``DeSP`` nanopore simulator."""
from __future__ import annotations

import random
from typing import Callable, Sequence

from .api import Simulator
from .random_utils import make_rng
from .simulator_utils import _run_external, _simulate_adapter
from .simulators import register_simulator as _register_simulator


class _DeSP:
    """Internal helper to invoke the ``desp`` binary."""

    command = "desp"

    @staticmethod
    def run(sequence: str) -> str:
        """Run ``desp`` on ``sequence`` via :func:`_run_external`."""
        return _run_external(_DeSP.command, sequence)


def simulate_desp(
    sequence: str,
    error_rate: float = 0.05,
    rng: random.Random | None = None,
    *,
    extra_args: Sequence[str] | None = None,
) -> str:
    """Use ``desp`` if available, else fall back to :func:`simulate_errors`."""

    if rng is None:
        rng = make_rng()

    return _simulate_adapter("desp", sequence, error_rate, rng, extra_args)


class DeSPChannel(Simulator):
    """Channel wrapper for the optional ``DeSP`` simulator."""

    def __init__(
        self,
        error_rate: float = 0.05,
        *,
        stage: str | None = None,
        options: Sequence[str] | None = None,
    ) -> None:
        self.error_rate = error_rate
        self.stage = stage.strip() if isinstance(stage, str) and stage.strip() else None
        if options is None:
            self.options: tuple[str, ...] = ()
        else:
            self.options = tuple(str(opt) for opt in options if str(opt))

    def simulate(self, sequence: str) -> str:
        extra_args: list[str] = []
        if self.stage:
            extra_args.extend(["--stage", self.stage])
        if self.options:
            extra_args.extend(self.options)
        return simulate_desp(
            sequence,
            error_rate=self.error_rate,
            rng=make_rng(),
            extra_args=extra_args or None,
        )


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    """Register the ``desp`` simulator."""

    registrar("desp", DeSPChannel())
