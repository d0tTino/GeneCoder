"""External CLI adapters for Illumina simulation."""
from __future__ import annotations

import logging
import shutil
import subprocess

from ...api import Simulator
from ...d2sim_adapter import simulate_d2sim
from ...simulator_utils import _parse_env_options, _run_external
from ...random_utils import make_rng


__all__ = [
    "IlluminaD2SimChannel",
    "IlluminaInSilicoSeqChannel",
    "simulate_insilicoseq",
]


class IlluminaD2SimChannel(Simulator):
    """Wrapper using the external ``d2sim`` simulator."""

    def __init__(self, error_rate: float = 0.05) -> None:
        self.error_rate = error_rate

    def simulate(self, sequence: str) -> str:
        return simulate_d2sim(sequence, error_rate=self.error_rate, rng=make_rng())


class IlluminaInSilicoSeqChannel(Simulator):
    """Use the ``insilicoseq`` CLI with a simple fallback."""

    def __init__(self, error_rate: float = 0.05, profile: str | None = None) -> None:
        self.error_rate = error_rate
        self.profile = profile

    def simulate(self, sequence: str) -> str:
        return simulate_insilicoseq(
            sequence, error_rate=self.error_rate, profile=self.profile
        )

    def with_profile(self, profile: str) -> "IlluminaInSilicoSeqChannel":
        """Return a new channel configured to use ``profile``."""

        return type(self)(error_rate=self.error_rate, profile=profile)


def simulate_insilicoseq(
    sequence: str,
    error_rate: float = 0.05,
    profile: str | None = None,
    *,
    seed: int | None = None,
) -> str:
    """Use the ``insilicoseq`` CLI if available, else fall back to ``IlluminaChannel``."""

    cmd = "insilicoseq"
    if shutil.which(cmd):
        cmd_list = [cmd, "-e", str(error_rate)]
        if profile:
            cmd_list += ["-p", profile]
        try:
            cmd_list += _parse_env_options(cmd)
            if seed is None:
                return _run_external(cmd_list, sequence)
            return _run_external(cmd_list, sequence, seed=seed)
        except (ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
            logging.getLogger(__name__).warning(
                "%s failed: %s; falling back to simple Illumina model",
                cmd,
                exc,
            )
    else:
        logging.getLogger(__name__).warning(
            "%s not found; falling back to simple Illumina model", cmd
        )

    from .channel import IlluminaChannel  # Local import to avoid cycles

    return IlluminaChannel(substitution_rate=error_rate).simulate(sequence)
